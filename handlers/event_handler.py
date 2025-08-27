"""
Discord Event Handler

This module handles all Discord.py events including message processing,
bot ready events, and other Discord API event handling.
"""

import asyncio
import traceback
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from discord_selfbot import SelfBot


class EventHandler:
    """Handles all Discord.py event processing"""
    
    def __init__(self, bot: 'SelfBot'):
        self.bot = bot
    
    async def handle_ready(self) -> None:
        """Handle bot ready event"""
        try:
            self.bot.log(f"Logged in as {self.bot.user}", "WARNING")
            self.bot.log("Bot is ready!", "WARNING")
            
            # Find and store target channels
            self.bot.log(f"Searching for channels in config: {self.bot.channel_ids}", "WARNING")
            
            for channel_id in self.bot.channel_ids:
                try:
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        self.bot.target_channels.append(channel)
                        self.bot.log(f"Found channel: {channel.name} ({channel.id})", "WARNING")
                    else:
                        self.bot.log(f"Channel not found: {channel_id}", "WARNING")
                except Exception as e:
                    self.bot.log(f"Error accessing channel {channel_id}: {str(e)}", "WARNING")
            
            self.bot.log(f"Total target channels found: {len(self.bot.target_channels)}", "WARNING")
            for ch in self.bot.target_channels:
                self.bot.log(f"Monitoring channel: {ch.name} ({ch.id})", "WARNING")
            
            # Start voice manager if available
            if hasattr(self.bot, 'voice_manager') and self.bot.voice_manager:
                await self.bot.voice_manager.start_voice_activity()
            
        except Exception as e:
            self.bot.log(f"On ready error: {str(e)}", "WARNING")
            self.bot.log(f"[DEBUG] Error details:\n{traceback.format_exc()}", "WARNING")
    
    async def handle_message(self, message) -> None:
        """Handle incoming message events"""
        try:
            # Skip messages from self
            if message.author == self.bot.user:
                return

            # Only process messages from target channels
            if str(message.channel.id) not in self.bot.channel_ids:
                return  # Skip messages from unmonitored channels
            
            # 👮‍♂️ ADMIN DETECTION - Check if message is from admin
            if hasattr(self.bot, 'admin_manager') and self.bot.admin_manager:
                is_admin = self.bot.admin_manager.check_admin_message(message)
                if is_admin:
                    # Admin detected, bot will go silent - no further processing
                    return
            
            # Check if bot should stay silent due to admin activity
            if hasattr(self.bot, 'admin_manager') and self.bot.admin_manager:
                if self.bot.admin_manager.should_bot_stay_silent():
                    # Bot is in admin silence mode
                    return

            # Log the message for debugging
            self.bot.log(f"Processing message in channel {message.channel.id} from {message.author.name}: {message.content}", "DEBUG")

            # Get and enhance message content
            content = await self._enhance_message_content(message)
            
            # Log the message
            self.bot.log(f"Message received in {message.channel.name}: {content}", "WARNING")
            
            # Check if bot should process this message
            if not self.bot.chat_manager.handle_message(message.author.id, content):
                return
                
            # Check if bot can send message (handles AFK state)
            if not self.bot.activity_manager.can_send_message():
                self.bot.log(f"Bot is {self.bot.activity_manager.current_state}, skipping message", "WARNING")
                return
                
            # Update message count
            self.bot.activity_manager.message_sent()
            
            # Process message through buffer system
            await self._process_message_buffer(message, content)
            
        except Exception as e:
            self.bot.log(f"Error processing message: {str(e)}", "WARNING")
            self.bot.log(f"Error details:\\n{traceback.format_exc()}", "WARNING")
    
    async def _enhance_message_content(self, message) -> str:
        """Enhance message content with mentions conversion and reply context"""
        # Get message content
        content = message.content
        
        # Convert mentions to readable names
        content = self.bot.convert_mentions_to_names(message)
        
        # Check if message is a reply
        is_reply = message.reference is not None
        
        if is_reply:
            try:
                # Get the message being replied to
                referenced_message = await message.channel.fetch_message(message.reference.message_id)
                # Add referenced message to content for context
                content = f"Previous message: {referenced_message.content}\\nCurrent message: {content}"
            except Exception as e:
                self.bot.log(f"Error fetching referenced message: {str(e)}", "DEBUG")
                pass
        
        return content
    
    async def _process_message_buffer(self, message, content: str) -> None:
        """Process message through the buffer system"""
        # Add message to buffer system
        user_id = str(message.author.id)
        if user_id not in self.bot.message_buffers:
            self.bot.message_buffers[user_id] = []
        
        self.bot.message_buffers[user_id].append({
            'content': content,  # Using the enhanced content with reply context
            'message': message
        })
        
        # Cancel existing delayed task if any
        if user_id in self.bot.delayed_tasks:
            self.bot.delayed_tasks[user_id].cancel()
        
        # Start new delayed task
        task = asyncio.create_task(self.bot.delayed_process(user_id))
        self.bot.delayed_tasks[user_id] = task
    
    def handle_socket_response(self, msg) -> None:
        """Handle socket response events (silently)"""
        pass  # Don't log socket responses
