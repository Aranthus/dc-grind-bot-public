import time
import logging
import asyncio
import discord

class ChatManager:
    def __init__(self, client=None, bot_config=None):
        """Initialize chat manager"""
        self.client = client
        self.bot_config = bot_config if bot_config else {}
        
        # Message queue system
        self.message_queue = asyncio.Queue()
        self.last_message_time = 0
        self.message_cooldown = self.bot_config.get('message_settings', {}).get('message_cooldown', 0)
        self.queue_processor_task = None
        
        # Logger setup - avoid duplicate handlers
        self.logger = logging.getLogger("ChatManager")
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            
            # Create console handler with a higher log level
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Create formatter and add it to the handler
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            console_handler.setFormatter(formatter)
            
            # Add handler to logger
            self.logger.addHandler(console_handler)

    async def start_queue_processor(self):
        """Start the message queue processor if not already running"""
        if self.queue_processor_task is None or self.queue_processor_task.done():
            if self.queue_processor_task and not self.queue_processor_task.done():
                self.queue_processor_task.cancel()
            self.queue_processor_task = asyncio.create_task(self.process_message_queue())
    
    async def stop_queue_processor(self):
        """Stop the message queue processor"""
        if self.queue_processor_task and not self.queue_processor_task.done():
            self.queue_processor_task.cancel()
            try:
                await self.queue_processor_task
            except asyncio.CancelledError:
                pass
            self.queue_processor_task = None

    async def process_message_queue(self):
        """Process messages in the queue with cooldown"""
        while True:
            try:
                # Get message from queue
                channel_id, content = await self.message_queue.get()
                
                # Check cooldown
                current_time = time.time()
                time_since_last = current_time - self.last_message_time
                
                if time_since_last < self.message_cooldown:
                    wait_time = self.message_cooldown - time_since_last
                    self.logger.info(f"[COOLDOWN] Waiting {wait_time:.1f} seconds before next message")
                    # Wait for the remaining cooldown time
                    await asyncio.sleep(wait_time)
                
                # Send message through Discord client
                if self.client and hasattr(self.client, 'get_channel'):
                    channel = self.client.get_channel(int(channel_id))
                    if channel:
                        try:
                            await channel.send(content)
                            self.last_message_time = time.time()
                        except discord.HTTPException as e:
                            if e.status == 429:  # Rate limit error
                                retry_after = e.retry_after
                                self.logger.warning(f"Rate limited. Waiting {retry_after} seconds before retrying...")
                                await asyncio.sleep(retry_after)
                                # Put message back in queue
                                await self.message_queue.put((channel_id, content))
                            else:
                                self.logger.error(f"Error sending message: {str(e)}")
                                await asyncio.sleep(1)
                
                # Mark task as done
                self.message_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error processing message queue: {str(e)}")
                await asyncio.sleep(1)

    async def send_message(self, channel_id, content):
        """Add message to the queue"""
        await self.message_queue.put((channel_id, content))
        await self.start_queue_processor()

    def get_user_name(self, user_id):
        """Get username from user ID"""
        if self.client:
            user = self.client.get_user(int(user_id))
            return user.name if user else str(user_id)
        return str(user_id)

    def handle_message(self, user_id, message):
        """
        Gelen mesajı işleyip işlememeye karar verir
        Returns:
            bool: True if message should be processed, False otherwise
        """
        # İlk temel kontroller
        if not message or not message.strip():
            return False
            
        # Bot'un kendi mesajlarını ignore et
        if hasattr(self.client, 'user') and self.client.user and user_id == self.client.user.id:
            return False
            
        # Çok kısa mesajları ignore et (spam olabilir)
        if len(message.strip()) < 2:
            return False
            
        # Rate limiting - aynı user'dan çok hızlı mesajlar
        current_time = time.time()
        if hasattr(self, 'last_user_message_times'):
            if user_id in self.last_user_message_times:
                time_diff = current_time - self.last_user_message_times[user_id]
                if time_diff < 1.0:  # 1 saniye minimum
                    return False
        else:
            self.last_user_message_times = {}
            
        self.last_user_message_times[user_id] = current_time
        return True
