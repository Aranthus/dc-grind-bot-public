"""
Message Processing Core Module

This module handles all message processing logic including AI responses,
message buffering, chunking, and reply decision making.
"""

import asyncio
import logging
import random
import re
import time
import traceback
from datetime import datetime
from typing import List, Dict, Optional, TYPE_CHECKING
from .conversation_strategy import ConversationStrategy

if TYPE_CHECKING:
    from discord_selfbot import SelfBot

# Constants (imported from main module)
DEFAULT_CHUNK_SIZE = 2000
MIN_TYPING_DURATION = 1
MAX_TYPING_DURATION = 8
MIN_WPM = 40
MAX_WPM = 80
TYPING_VARIATION_MIN = 0.8
TYPING_VARIATION_MAX = 1.2


class MessageProcessor:
    """Handles all message processing operations for the bot"""
    
    def __init__(self, bot: 'SelfBot'):
        self.bot = bot
        self.memory_manager = None  # Will be initialized when bot starts
        self.gif_manager = None  # Will be initialized when bot starts
        self.context_cache = {}  # Cache for active users
        self.user_sessions = {}  # Track user chat sessions {user_id: last_interaction_time}
        self.session_timeout = 3600  # 1 hour session timeout
        self.conversation_strategy = ConversationStrategy(bot)  # 🎯 Anti-hijack system
    
    async def process_message_buffer(self, user_id: int) -> None:
        """Process message buffer for a user"""
        try:
            self.bot.log(f"[DEBUG] ======== Buffer Processing Started ========", "WARNING")
            self.bot.log(f"[DEBUG] Processing buffer for user: {user_id}", "WARNING")
            
            if not self.bot.message_buffers.get(user_id):
                self.bot.log(f"[DEBUG] No messages in buffer for user {user_id}", "WARNING")
                return

            # Get messages from buffer
            messages = [msg['content'] for msg in self.bot.message_buffers[user_id]]
            original_message = self.bot.message_buffers[user_id][-1]['message']
            
            self.bot.log(f"[DEBUG] Number of messages in buffer: {len(messages)}", "WARNING")
            self.bot.log(f"[DEBUG] Messages in buffer: {messages}", "WARNING")
            
            # Clear buffer
            self.bot.message_buffers[user_id] = []
            self.bot.log("[DEBUG] Buffer cleared", "WARNING")
            
            # Get combined message
            combined_message = self.combine_messages(messages)
            self.bot.log(f"[DEBUG] Combined message: {combined_message}", "WARNING")
            
            # Check if we should reply
            is_mention = self.bot.user.mentioned_in(original_message)
            is_reply = bool(original_message.reference and original_message.reference.resolved)
            
            # Check if reply is specifically to bot
            is_reply_to_bot = False
            if is_reply and original_message.reference.resolved:
                referenced_msg = original_message.reference.resolved
                is_reply_to_bot = referenced_msg.author.id == self.bot.user.id
                self.bot.log(f"[DEBUG] Reply to bot: {is_reply_to_bot} (referenced author: {referenced_msg.author.name})", "WARNING")
            
            reply_chain_length = self.bot.reply_chain_count.get(user_id, 0)
            
            should_reply = self.should_reply(original_message, is_mention, is_reply, reply_chain_length, is_reply_to_bot)
            self.bot.log(f"[DEBUG] Should reply decision: {should_reply}", "WARNING")
            
            if should_reply:
                await self._process_ai_response(original_message, combined_message, user_id, is_mention, is_reply)
                
        except Exception as e:
            self.bot.log(f"[DEBUG] Buffer processing error: {str(e)}", "WARNING")
            self.bot.log(f"[DEBUG] Error details:\n{traceback.format_exc()}", "WARNING")
        finally:
            self.bot.log(f"[DEBUG] ======== Buffer Processing Complete ========", "WARNING")
    
    async def _process_ai_response(self, original_message, combined_message: str, user_id: int, is_mention: bool, is_reply: bool) -> None:
        """Process AI response and send messages"""
        self.bot.log("[DEBUG] Getting AI response...", "WARNING")
        try:
            # EXPERIMENTAL: Check if bot should intervene in this conversation
            should_respond = await self._should_bot_respond(original_message, combined_message, is_mention, is_reply)
            if not should_respond:
                self.bot.log("[DEBUG] Decision: Bot should not respond to this conversation", "WARNING")
                return
            
            # Get AI response
            response = await self.get_ai_response(original_message.author, combined_message)
            self.bot.log(f"[DEBUG] AI response received: {response}", "WARNING")
            
            # Process GIF commands if GIF manager is available
            if response and self.gif_manager:
                original_response = response
                channel_id = original_message.channel.id if original_message.channel else None
                response = await self.gif_manager.process_gif_message(response, channel_id)
                if response != original_response:
                    self.bot.log(f"[DEBUG] GIF processing applied to response", "WARNING")
            
            if response:
                
                # Split response into chunks
                chunks = self.split_into_chunks(response)
                self.bot.log(f"[DEBUG] Split response into {len(chunks)} chunks", "WARNING")
                
                # Use reply feature only for direct replies and mentions
                use_reply = is_reply or (is_mention and self.bot.user.mentioned_in(original_message))
                if use_reply:
                    self.bot.log("[DEBUG] Using reply feature for this message", "WARNING")
                else:
                    self.bot.log("[DEBUG] Sending as normal message", "WARNING")
                
                sent_messages = await self._send_message_chunks(original_message, chunks, use_reply)
                await self._handle_message_editing(sent_messages)
                
        except Exception as e:
            self.bot.log(f"[DEBUG] Error in AI response process: {str(e)}", "WARNING")
            self.bot.log(f"[DEBUG] Error details:\n{traceback.format_exc()}", "WARNING")
    
    async def _send_message_chunks(self, original_message, chunks: List[str], use_reply: bool) -> List:
        """Send message chunks with typing simulation"""
        sent_messages = []
        for i, chunk in enumerate(chunks):
            # Calculate typing duration
            typing_duration = self.calculate_typing_duration(chunk)
            self.bot.log(f"[DEBUG] Sending chunk {i+1}/{len(chunks)}", "WARNING")
            self.bot.log(f"[DEBUG] Typing duration: {typing_duration} seconds", "WARNING")
            
            try:
                async with original_message.channel.typing():
                    await asyncio.sleep(typing_duration)
                
                if use_reply and i == 0:
                    sent_msg = await original_message.reply(chunk, mention_author=True)
                else:
                    sent_msg = await original_message.channel.send(chunk)
                    
                sent_messages.append(sent_msg)
                self.bot.log(f"[DEBUG] Sent chunk successfully: {chunk}", "WARNING")
                
            except Exception as e:
                self.bot.log(f"[DEBUG] Error sending message chunk: {str(e)}", "WARNING")
                self.bot.log(f"[DEBUG] Error details:\n{traceback.format_exc()}", "WARNING")
                continue
        
        return sent_messages
    
    async def _handle_message_editing(self, sent_messages: List) -> None:
        """Handle random message editing"""
        # Get edit probability from config (default 6%)
        edit_prob = getattr(self.bot.bot_config.settings, 'edit_probability', 0.06)
        if sent_messages and random.random() < edit_prob:
            try:
                # Wait for configured time before editing
                min_wait = self.bot.edit_wait_time.get('min', 1.0)
                max_wait = self.bot.edit_wait_time.get('max', 3.0)
                await asyncio.sleep(random.uniform(min_wait, max_wait))
                
                # Randomly select which message to edit
                msg_to_edit = random.choice(sent_messages)
                original_content = msg_to_edit.content
                
                # Choose edit type
                edit_type = random.choice([
                    "typo",        # Fix a typo
                    "addition",    # Add something
                    "correction"   # Correct something
                ])
                
                edited_content = self._apply_edit(original_content, edit_type)
                if edited_content != original_content:
                    await msg_to_edit.edit(content=edited_content)
                    self.bot.log(f"[DEBUG] Edited message: {edit_type}", "WARNING")
                    
            except Exception as e:
                self.bot.log(f"[DEBUG] Error editing message: {str(e)}", "WARNING")
    
    def _apply_edit(self, content: str, edit_type: str) -> str:
        """Apply edit to message content"""
        if edit_type == "typo":
            # Simple typo corrections
            typo_fixes = {
                "teh": "the", "hte": "the", "adn": "and", "nad": "and",
                "taht": "that", "thsi": "this", "jsut": "just", "dont": "don't"
            }
            for typo, fix in typo_fixes.items():
                content = content.replace(typo, fix)
        
        elif edit_type == "addition":
            # Add common additions
            additions = [" lol", " haha", " 😅", " btw"]
            if random.random() < 0.3:  # 30% chance
                content += random.choice(additions)
        
        elif edit_type == "correction":
            # Simple corrections
            if "your" in content.lower() and random.random() < 0.5:
                content = content.replace("your", "you're")
        
        return content
    
    async def get_ai_response(self, user, message_content: str) -> Optional[str]:
        """Get response from AI provider with full context awareness"""
        try:
            if not self.bot.activity_manager.can_send_message():
                self.bot.logger.info(f"Bot is {self.bot.activity_manager.current_state}, skipping...")
                return None
            
            # Get base system prompt
            from prompts import get_prompt
            prompt_type = self.bot.bot_config.settings.prompt_type
            base_system_prompt = get_prompt(prompt_type)
            
            # Get username and format message
            display_name = user.display_name if hasattr(user, 'display_name') else user.name
            formatted_message = f"{display_name}: {message_content}"
            
            self.bot.log(f"[DEBUG] User Message: {formatted_message}", "WARNING")
            
            # 🧠 SMART CONTEXT MANAGEMENT
            current_time = time.time()
            user_id_str = str(user.id)
            
            # Check if this is first interaction or session expired
            is_new_session = (
                user_id_str not in self.user_sessions or 
                (current_time - self.user_sessions[user_id_str]) > self.session_timeout
            )
            
            if is_new_session:
                # First message or expired session: Load full context
                self.bot.log(f"🆕 NEW SESSION for {display_name} - loading full context", "WARNING")
                enhanced_system_prompt = await self._build_contextual_prompt(
                    user.id, display_name, message_content, base_system_prompt
                )
            else:
                # Existing session: Use basic prompt (AI has history)
                self.bot.log(f"📱 EXISTING SESSION for {display_name} - using basic prompt", "WARNING")
                enhanced_system_prompt = base_system_prompt
            
            # Update session timestamp
            self.user_sessions[user_id_str] = current_time
            
            # Generate AI response with enhanced context
            if hasattr(self.bot.ai_provider, 'supports_temperature') and self.bot.ai_provider.supports_temperature:
                response = await self.bot.ai_provider.generate_response(
                    enhanced_system_prompt,
                    formatted_message,
                    user_id=user.id,
                    temperature=self.bot.temperature
                )
            else:
                response = await self.bot.ai_provider.generate_response(
                    enhanced_system_prompt,
                    formatted_message,
                    user_id=user.id
                )
            
            # 📝 SAVE TO MEMORY (Background task)
            if response and self.memory_manager:
                asyncio.create_task(self._save_conversation_memory(
                    user.id, display_name, message_content, response
                ))
            
            if response:
                response = self.clean_message(response)
                return response
            else:
                return "AI yanıt vermedi"
                
        except Exception as e:
            self.bot.logger.error(f"Error getting AI response: {e}")
            return "Hata oluştu"
    
    async def _build_contextual_prompt(self, user_id: str, username: str, message: str, base_prompt: str) -> str:
        """Build enhanced system prompt with user context"""
        try:
            if not self.memory_manager:
                self.bot.log("❌ NO MEMORY MANAGER - using basic prompt", "WARNING")
                return base_prompt
            
            self.bot.log(f"🧠 BUILDING CONTEXT for user {username} ({user_id})", "WARNING")
            
            # Check cache first (performance)
            cache_key = f"{user_id}_context"
            if cache_key in self.context_cache:
                cached_context = self.context_cache[cache_key]
                # Cache is valid for 10 minutes
                if (datetime.now() - cached_context['timestamp']).seconds < 600:
                    user_context = cached_context['data']
                else:
                    user_context = await self.memory_manager.get_user_context(user_id)
                    self.context_cache[cache_key] = {
                        'data': user_context,
                        'timestamp': datetime.now()
                    }
            else:
                user_context = await self.memory_manager.get_user_context(user_id, limit=20)
                self.context_cache[cache_key] = {
                    'data': user_context,
                    'timestamp': datetime.now()
                }
            
            # Extract topics for relevance
            current_topics = await self.memory_manager.extract_topics(message)
            self.bot.log(f"📊 USER CONTEXT: has_history={user_context['has_history']}, recent_count={len(user_context['recent_conversations'])}", "WARNING")
            
            # Build contextual enhancement
            context_enhancement = await self._generate_context_prompt(
                user_context, username, current_topics, message
            )
            
            # Combine prompts
            enhanced_prompt = f"{base_prompt}\n\n{context_enhancement}"
            self.bot.log(f"🎯 ENHANCED PROMPT LENGTH: {len(enhanced_prompt)} chars", "WARNING")
            self.bot.log(f"📝 CONTEXT CONTENT: {context_enhancement[:800]}...", "WARNING")
            
            return enhanced_prompt
            
        except Exception as e:
            self.bot.log(f"Error building context: {e}", "WARNING")
            return base_prompt  # Fallback to basic prompt
    
    async def _generate_context_prompt(self, user_context, username, topics, current_message):
        """Generate contextual prompt section"""
        if not user_context['has_history']:
            return f"Note: This is your first conversation with {username}. Be friendly and natural."
        
        user_memory = user_context['user_memory']
        recent_convos = user_context['recent_conversations'][:10]
        
        # Build relationship context
        relationship = self._describe_relationship(user_memory.get('relationship_strength', 0.1))
        interests = user_memory.get('preferred_topics', [])
        style = user_memory.get('conversation_style', 'casual')
        
        # Build conversation history summary with time-based filtering
        history_summary = ""
        fresh_context = ""
        old_context = ""
        
        if recent_convos:
            current_time = time.time()
            for convo in recent_convos:
                timestamp = convo.get('timestamp')
                time_diff = current_time - timestamp if timestamp else 999999
                time_ago = self._time_ago(timestamp)
                content_snippet = convo.get('message_content', '')[:200]
                
                # 5 dakika = 300 saniye
                if time_diff <= 300:  # Fresh context (son 5 dakika)
                    fresh_context += f"- {time_ago}: {content_snippet}...\n"
                else:  # Old context (5 dakikadan eski)
                    old_context += f"- {time_ago}: {content_snippet}...\n"
            
            if fresh_context:
                history_summary = f"\nRecent conversation (FRESH - respond naturally):\n{fresh_context}"
            
            if old_context:
                history_summary += f"\nOld conversation (5+ min ago - treat as STALE, respond to current message only):\n{old_context}"
        
        # Topic continuity
        topic_context = ""
        if any(topic in interests for topic in topics):
            shared_topics = [t for t in topics if t in interests]
            topic_context = f"\nNote: {username} is interested in {', '.join(shared_topics)}."
        
        # Add project context if available
        project_context = ""
        if hasattr(self.bot, 'project_manager') and self.bot.project_manager:
            project_info = self.bot.project_manager.get_project_context()
            if project_info:
                project_context = f"\n\n{project_info}"
        
        # Add server knowledge context if available
        server_knowledge_context = ""
        if hasattr(self.bot, 'server_knowledge_manager') and self.bot.server_knowledge_manager:
            channels_info = self.bot.server_knowledge_manager.get_all_channels_info()
            if channels_info:
                server_knowledge_context = f"\n\n{channels_info}"
    
        context_prompt = f"""
=== CONVERSATION CONTEXT ===
You're talking with {username} ({relationship}).
Their style: {style}
Their interests: {', '.join(interests[:3]) if interests else 'getting to know them'}
{history_summary}{topic_context}{project_context}{server_knowledge_context}

🚨 CRITICAL CONTEXT RULES:
- FRESH context (0-5 min): You can reference these naturally
- STALE context (5+ min): IGNORE completely, treat current message as fresh conversation
- If all context is STALE, respond like you're meeting them fresh
- Never mention "I remember from earlier" for STALE context
- Match their conversation style ({style})
- Don't mention that you have "memory" or "remember from database"
=== END CONTEXT ==="""
        
        return context_prompt
    
    async def _save_conversation_memory(self, user_id, username, message_content, bot_response):
        """Save conversation to memory (background task)"""
        try:
            if not self.memory_manager:
                return
            
            # Extract metadata
            topics = await self.memory_manager.extract_topics(message_content)
            message_type = self._classify_message_type(message_content)
            sentiment = self._analyze_sentiment(message_content)
            
            # Save to database with both response content AND bot username
            bot_username = getattr(self.bot, 'bot_name', 'unknown_bot')
            
            await self.memory_manager.save_conversation(
                channel_id=str(getattr(self.bot, 'current_channel_id', 'unknown')),
                user_id=user_id,
                username=username,
                message_content=message_content,
                bot_response=bot_response,  # Keep actual response text
                bot_username=bot_username,  # Add bot username as separate field
                message_type=message_type,
                topics=topics,
                sentiment=sentiment
            )
            
            # Invalidate cache for next interaction
            cache_key = f"{user_id}_context"
            if cache_key in self.context_cache:
                del self.context_cache[cache_key]
                
        except Exception as e:
            self.bot.log(f"Error saving memory: {e}", "WARNING")
    
    def _describe_relationship(self, strength: float) -> str:
        """Convert relationship strength to description"""
        if strength < 0.2:
            return "new person"
        elif strength < 0.5:
            return "acquaintance"
        elif strength < 0.8:
            return "friend"
        else:
            return "close friend"
    
    def _time_ago(self, timestamp: str) -> str:
        """Format time ago with proper timezone handling"""
        try:
            from datetime import datetime, timezone
            import time
            
            # Handle different timestamp formats
            if isinstance(timestamp, (int, float)):
                # Unix timestamp
                past_time = timestamp
            elif isinstance(timestamp, str):
                # ISO format string
                if 'T' in timestamp:
                    past = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    past_time = past.timestamp()
                else:
                    # Try parsing as timestamp string
                    past_time = float(timestamp)
            else:
                return "unknown time"
            
            # Calculate difference in seconds
            current_time = time.time()
            diff_seconds = int(current_time - past_time)
            
            self.bot.log(f"[DEBUG] Time calc: current={current_time}, past={past_time}, diff={diff_seconds}s", "WARNING")
            
            if diff_seconds < 0:
                return "future?"
            elif diff_seconds < 60:
                return "just now"
            elif diff_seconds < 3600:
                minutes = diff_seconds // 60
                return f"{minutes}min ago"
            elif diff_seconds < 86400:
                hours = diff_seconds // 3600
                return f"{hours}h ago"
            else:
                days = diff_seconds // 86400
                return f"{days}d ago"
                
        except Exception as e:
            self.bot.log(f"[ERROR] Time parsing failed for '{timestamp}': {e}", "WARNING")
            return "unknown time"
    
    def _classify_message_type(self, message: str) -> str:
        """Classify message type"""
        message_lower = message.lower()
        if any(greeting in message_lower for greeting in ['hello', 'hi', 'hey', 'sup']):
            return 'greeting'
        elif '?' in message:
            return 'question'
        elif any(word in message_lower for word in ['crypto', 'bitcoin', 'market']):
            return 'topic_change'
        else:
            return 'casual'
    
    def _analyze_sentiment(self, message: str) -> str:
        """Basic sentiment analysis"""
        positive_words = ['good', 'great', 'awesome', 'nice', 'cool', 'love', 'like']
        negative_words = ['bad', 'terrible', 'hate', 'suck', 'awful', 'damn']
        
        message_lower = message.lower()
        pos_count = sum(1 for word in positive_words if word in message_lower)
        neg_count = sum(1 for word in negative_words if word in message_lower)
        
        if pos_count > neg_count:
            return 'positive'
        elif neg_count > pos_count:
            return 'negative'
        else:
            return 'neutral'
    
    def split_into_chunks(self, text: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> List[str]:
        """Split text into chunks"""
        if not text:
            return []
            
        # Check if chunking is disabled (default to False if not set)
        disable_chunking = getattr(self.bot.bot_config.settings.ai_settings, 'disable_chunking', False)
        if disable_chunking:
            return [text]
        
        # Get chunk size from config (use default if not set)
        chunk_size = getattr(self.bot.bot_config.settings.ai_settings, 'chunk_size', DEFAULT_CHUNK_SIZE)
        
        # If text is shorter than chunk size, return as is
        if len(text) <= chunk_size:
            return [text]
            
        chunks = []
        current_chunk = ""
        
        for line in text.split('\n'):
            if len(current_chunk) + len(line) + 1 <= chunk_size:
                current_chunk += line + '\n'
            else:
                chunks.append(current_chunk.strip())
                current_chunk = line + '\n'
                
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks
    
    def clean_message(self, message: str) -> str:
        """Clean message content"""
        if not message:
            return ""
        
        # Remove extra whitespace
        message = re.sub(r'\s+', ' ', message.strip())
        
        # Remove surrounding quotes from AI responses
        message = message.strip('"')
        message = message.strip("'")
        
        # Remove markdown formatting that might break Discord
        message = re.sub(r'\*\*(.*?)\*\*', r'\1', message)  # Remove bold
        message = re.sub(r'\*(.*?)\*', r'\1', message)      # Remove italic
        message = re.sub(r'`(.*?)`', r'\1', message)        # Remove code
        
        # Remove any potential mentions that shouldn't be there
        message = re.sub(r'<@[!&]?\d+>', '', message)
        
        # Remove common AI prefixes/suffixes
        message = re.sub(r'^(Here\'s|Here is)\s+', '', message, flags=re.IGNORECASE)
        message = re.sub(r'^(Answer:|Response:)\s+', '', message, flags=re.IGNORECASE)
        
        # Limit length
        if len(message) > 2000:
            message = message[:1997] + "..."
        
        return message.strip()
    
    def combine_messages(self, messages: List[str]) -> str:
        """Combine multiple messages into one"""
        if not messages:
            return ""
        
        if len(messages) == 1:
            return messages[0]
        
        # Join messages with space, removing duplicates
        combined = " ".join(messages)
        
        # Remove excessive repetition
        words = combined.split()
        cleaned_words = []
        for word in words:
            if not cleaned_words or word != cleaned_words[-1]:
                cleaned_words.append(word)
        
        return " ".join(cleaned_words)
    
    def should_reply(self, message, is_mention: bool, is_reply: bool, reply_chain_length: int, is_reply_to_bot: bool = False) -> bool:
        """Determine if bot should reply to a message using advanced conversation strategy"""
        # Get reply chances
        reply_chances = self.bot.reply_chances
        
        # Determine message type and get base chance
        if is_mention:
            if "@everyone" in message.content or "@here" in message.content:
                base_chance = reply_chances.get('group_mention', 1.0)
            else:
                base_chance = reply_chances.get('direct_mention', 1.0)
        elif is_reply_to_bot:
            # Reply directly to bot's message = 100% chance  
            base_chance = reply_chances.get('reply_to_bot', 1.0)
        elif message.content.endswith('?'):
            base_chance = reply_chances.get('question', 1.0)
        elif reply_chain_length > 0:
            base_chance = reply_chances.get('reply_chain', 1.0)
        else:
            base_chance = reply_chances.get('normal_chat', 1.0)
        
        # 🎯 ADVANCED CONVERSATION STRATEGY
        # Use tri-layer analysis to prevent hijacking private conversations
        should_reply, analysis_score = self.conversation_strategy.analyze_should_reply(
            message, is_mention, is_reply_to_bot, base_chance
        )
        
        return should_reply
    
    def calculate_typing_duration(self, message: str) -> float:
        """Calculate realistic typing duration"""
        # Average typing speed: MIN_WPM-MAX_WPM WPM (Words Per Minute)
        words = len(message.split())
        base_time = words * (60 / random.randint(MIN_WPM, MAX_WPM))  # In seconds
        
        # Add random variation (20%)
        variation = random.uniform(TYPING_VARIATION_MIN, TYPING_VARIATION_MAX)
        typing_time = base_time * variation
        
        # Minimum and maximum duration limits
        return max(MIN_TYPING_DURATION, min(typing_time, MAX_TYPING_DURATION))
    
    async def send_message(self, message: str, channel) -> Optional[object]:
        """Send a message to a channel with typing simulation"""
        try:
            # Clean the message
            message = self.clean_message(message)
            
            # Calculate typing duration
            typing_duration = self.calculate_typing_duration(message)
            
            # Show typing indicator
            async with channel.typing():
                await asyncio.sleep(typing_duration)
            
            # Send message
            return await channel.send(message)
            
        except Exception as e:
            self.bot.log(f"Error sending message: {str(e)}", "ERROR")
            return None
            
            self.bot.log(f"[DEBUG] Processing message content: {message_content}", "WARNING")
            
            # Get the response from AI
            response = await self.get_ai_response(message.author, message_content)
            
            if response:
                # Clean the response
                response = self.clean_message(response)
                
                # Split response into chunks
                chunks = self.split_into_chunks(response)
                
                for chunk in chunks:
                    # Calculate typing duration
                    typing_duration = max(2, len(chunk) * 0.2)
                    
                    # Show typing effect
                    async with message.channel.typing():
                        await asyncio.sleep(typing_duration)
                    
                    # Send message
                    await message.channel.send(chunk)
                    
                    # Wait between chunks
                    if chunk != chunks[-1]:  # Not the last chunk
                        await asyncio.sleep(random.uniform(1.5, 3))
                
                # Update message count
                self.bot.activity_manager.message_sent()
                
                # Log status
                status = self.bot.activity_manager.get_status()
                self.bot.log(
                    f"Message sent - Status: {status['state'].upper()}, " +
                    f"Count: {status['message_count']}/{status['max_messages']}",
                    "INFO"
                )
                
        except Exception as e:
            self.bot.log(f"Error processing message: {str(e)}", "ERROR")
    
    # 🎯 SESSION MANAGEMENT HELPERS
    def reset_user_session(self, user_id: str) -> None:
        """Force reset a user's session (for testing/debugging)"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
            self.bot.log(f"🔄 Session reset for user {user_id}", "WARNING")
    
    def cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions to free memory"""
        current_time = time.time()
        expired_users = [
            user_id for user_id, last_time in self.user_sessions.items()
            if (current_time - last_time) > self.session_timeout
        ]
        
        for user_id in expired_users:
            del self.user_sessions[user_id]
        
        if expired_users:
            self.bot.log(f"🧹 Cleaned up {len(expired_users)} expired sessions", "INFO")
    
    def get_session_stats(self) -> dict:
        """Get session statistics for monitoring"""
        current_time = time.time()
        active_sessions = sum(
            1 for last_time in self.user_sessions.values()
            if (current_time - last_time) <= self.session_timeout
        )
        
        return {
            'total_sessions': len(self.user_sessions),
            'active_sessions': active_sessions,
            'session_timeout': self.session_timeout
        }
    
    async def _should_bot_respond(self, original_message, combined_message: str, is_mention: bool, is_reply: bool) -> bool:
        """Decide if bot should respond to this conversation (EXPERIMENTAL)"""
        try:
            # Check if conversation intelligence is enabled
            conv_intelligence = self.bot.original_config.get('settings', {}).get('conversation_intelligence', {})
            if not conv_intelligence.get('enabled', False):
                self.bot.log("[DEBUG] Conversation intelligence disabled, responding normally", "WARNING")
                return True
            
            # Always respond to direct mentions and replies
            if is_mention or is_reply:
                self.bot.log("[DEBUG] Decision: Always respond to mentions/replies", "WARNING")
                return True
            
            # Get recent channel history for context
            recent_messages = []
            if original_message.channel:
                async for msg in original_message.channel.history(limit=8, before=original_message):
                    if msg.author.bot:
                        continue  # Skip bot messages
                    recent_messages.insert(0, f"{msg.author.display_name}: {msg.content}")
            
            # Build decision prompt
            context = "\n".join(recent_messages[-5:])  # Last 5 messages
            new_message = f"{original_message.author.display_name}: {original_message.content}"
            
            decision_prompt = f"""Analyze this Discord conversation and decide if you (a bot) should respond.

Recent messages:
{context}

New message:
{new_message}

Decision rules:
- ALWAYS respond if: Message contains @god2god0 (direct mention), reply to your message, someone asks you a direct question
- Respond if: General question to everyone, asking for help, discussing topics you can contribute to
- Don't respond if: Private conversation between 2 people (unless they mention/reply to you), personal chat already being handled by others

Should you respond?
Answer: YES or NO
Brief reason: (one sentence)"""
            
            # Get decision from AI (this response is NOT sent to Discord)
            decision_response = await self._get_decision_from_ai(decision_prompt)
            
            # Parse decision
            should_respond = "YES" in decision_response.upper()
            self.bot.log(f"[DEBUG] Decision AI response: {decision_response}", "WARNING")
            self.bot.log(f"[DEBUG] Decision: {'RESPOND' if should_respond else 'STAY_SILENT'}", "WARNING")
            
            return should_respond
            
        except Exception as e:
            self.bot.log(f"[DEBUG] Error in decision making, defaulting to respond: {e}", "WARNING")
            return True  # Default to responding if decision fails
    
    async def _get_decision_from_ai(self, decision_prompt: str) -> str:
        """Get a simple decision from AI (separate from main chat)"""
        try:
            # Use the same AI provider but for decision making only
            if hasattr(self.bot, 'ai_provider') and self.bot.ai_provider:
                response = await self.bot.ai_provider.get_response(
                    prompt=decision_prompt, 
                    message=decision_prompt,
                    system_prompt="You are a helpful assistant that makes YES/NO decisions.",
                    max_tokens=50
                )
                return response.strip()
            else:
                self.bot.log("[DEBUG] No AI provider available for decision", "WARNING")
                return "YES"  # Default to responding
                
        except Exception as e:
            self.bot.log(f"[DEBUG] Error getting AI decision: {e}", "WARNING")
            return "YES"  # Default to responding if error
