"""
🎯 Conversation Strategy Module
Advanced anti-hijack system for Discord bot to prevent interrupting private conversations.

Combines 3 strategies:
1. Reply Chain Tracking - Analyze conversation patterns
2. Timing-Based Detection - Detect rapid conversations  
3. Context Analysis - Understand conversation participants

Author: Enhanced Discord Bot System
"""

import time
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta


class ConversationStrategy:
    """Smart conversation analysis to prevent bot hijacking private chats"""
    
    def __init__(self, bot):
        self.bot = bot
        self.conversation_history = {}  # channel_id: [messages with timestamps]
        self.history_limit = 10  # Keep last 10 messages per channel
        self.rapid_response_threshold = 30  # seconds
        self.conversation_timeout = 300  # 5 minutes
    
    def analyze_should_reply(self, message, is_mention: bool, is_reply_to_bot: bool, base_chance: float) -> tuple[bool, float]:
        """
        Main analysis function combining all 3 strategies
        Returns: (should_reply: bool, final_score: float)
        """
        # 🔥 GUARANTEED REPLIES - No analysis needed
        if is_mention or is_reply_to_bot:
            self.bot.log(f"🎯 GUARANTEED REPLY: mention={is_mention}, reply_to_bot={is_reply_to_bot}", "WARNING")
            return True, 1.0
        
        # 📊 STORE MESSAGE for analysis
        self._store_message(message)
        
        # 🧠 TRI-LAYER ANALYSIS
        chain_penalty = self._analyze_reply_chain(message)
        timing_penalty = self._analyze_timing(message)  
        context_penalty = self._analyze_context(message)
        
        # 🎯 CALCULATE FINAL SCORE
        final_score = base_chance * chain_penalty * timing_penalty * context_penalty
        should_reply = final_score > 0.05  # Minimum threshold
        
        # 📝 DEBUG LOGGING
        self.bot.log(
            f"🧠 CONVERSATION ANALYSIS for {message.author.name}:\n"
            f"   Base chance: {base_chance:.3f}\n"
            f"   Chain penalty: {chain_penalty:.3f}\n" 
            f"   Timing penalty: {timing_penalty:.3f}\n"
            f"   Context penalty: {context_penalty:.3f}\n"
            f"   Final score: {final_score:.4f}\n"
            f"   Decision: {'REPLY' if should_reply else 'SKIP'}", 
            "WARNING"
        )
        
        return should_reply, final_score
    
    def _store_message(self, message):
        """Store message for conversation analysis"""
        channel_id = message.channel.id
        
        if channel_id not in self.conversation_history:
            self.conversation_history[channel_id] = []
        
        # Add message with metadata
        msg_data = {
            'id': message.id,
            'author_id': message.author.id,
            'author_name': message.author.name,
            'content': message.content,
            'timestamp': time.time(),
            'is_bot': message.author.id == self.bot.user.id,
            'reply_to': message.reference.message_id if message.reference else None
        }
        
        # Add to history and maintain limit
        self.conversation_history[channel_id].append(msg_data)
        if len(self.conversation_history[channel_id]) > self.history_limit:
            self.conversation_history[channel_id] = self.conversation_history[channel_id][-self.history_limit:]
    
    def _analyze_reply_chain(self, message) -> float:
        """
        🔗 REPLY CHAIN TRACKING
        Analyze conversation patterns to detect private conversations
        Returns penalty multiplier (0.1 = high penalty, 1.0 = no penalty)
        """
        channel_id = message.channel.id
        history = self.conversation_history.get(channel_id, [])
        
        if len(history) < 3:
            return 0.8  # Not enough data, slight penalty
        
        # Get last 5 messages
        recent = history[-5:]
        
        # Count unique participants (excluding bot)
        participants = set()
        bot_involved = False
        bot_user_id = str(getattr(self.bot.user, 'id', None)) if hasattr(self.bot, 'user') else None
        
        for msg in recent:
            if msg['is_bot'] or str(msg['author_id']) == bot_user_id:
                bot_involved = True
            else:
                participants.add(msg['author_id'])
        
        participant_count = len(participants)
        
        # 🎯 PATTERN ANALYSIS
        if participant_count == 2 and not bot_involved:
            # Check if bot has been silent for too long (conversation orphan)
            bot_silence_duration = self._get_bot_silence_duration(channel_id)
            if bot_silence_duration > 1800:  # 30 minutes of bot silence
                self.bot.log(f"🔇 BOT ORPHAN detected: {bot_silence_duration/60:.1f}min silence - ENCOURAGING JOIN", "WARNING")
                return 0.5  # Reduced penalty - encourage natural joining
            else:
                # Two people talking, bot not involved = Private conversation
                self.bot.log(f"🔒 PRIVATE CONVERSATION detected: {participant_count} participants, bot not involved", "WARNING")
                return 0.1  # 90% penalty
        
        elif participant_count == 2 and bot_involved:
            # Two people + bot = Natural conversation
            return 0.7  # 30% penalty
            
        elif participant_count >= 3:
            # Group conversation = More natural to join
            return 0.6  # 40% penalty
            
        else:
            # Single person or unclear pattern
            return 0.8  # 20% penalty
    
    def _analyze_timing(self, message) -> float:
        """
        ⏰ TIMING-BASED DETECTION  
        Detect rapid back-and-forth conversations
        Returns penalty multiplier (0.2 = high penalty, 1.0 = no penalty)
        """
        channel_id = message.channel.id
        history = self.conversation_history.get(channel_id, [])
        
        if len(history) < 2:
            return 1.0  # No timing data
        
        current_time = time.time()
        last_msg = history[-2]  # Previous message
        
        # Time since last message
        time_gap = current_time - last_msg['timestamp']
        
        # Check for rapid conversation pattern in last 3-4 messages
        rapid_count = 0
        for i in range(len(history) - 1, max(0, len(history) - 4), -1):
            if i > 0:
                gap = history[i]['timestamp'] - history[i-1]['timestamp']
                if gap <= self.rapid_response_threshold:
                    rapid_count += 1
        
        # 🎯 TIMING RULES
        if time_gap <= 15:  # Very rapid response (<15 sec)
            self.bot.log(f"⚡ RAPID RESPONSE detected: {time_gap:.1f}s gap", "WARNING")
            return 0.2  # 80% penalty - don't interrupt rapid chat
            
        elif time_gap <= self.rapid_response_threshold and rapid_count >= 2:
            # Multiple rapid responses = Active conversation
            self.bot.log(f"🔥 ACTIVE CONVERSATION detected: {rapid_count} rapid messages", "WARNING")
            return 0.3  # 70% penalty
            
        elif time_gap <= 120:  # Normal conversation pace (2 min)
            return 0.6  # 40% penalty
            
        elif time_gap > self.conversation_timeout:
            # Long pause = Conversation likely ended, ENCOURAGE bot participation
            self.bot.log(f"💤 CONVERSATION PAUSE detected: {time_gap/60:.1f}min gap - SAFE TO JOIN", "WARNING")
            return 1.2  # 20% BONUS - actively encourage joining after pauses
            
        elif time_gap > 180:  # 3+ minutes = Natural join opportunity
            self.bot.log(f"🌱 NATURAL JOIN OPPORTUNITY: {time_gap/60:.1f}min gap", "WARNING")
            return 1.0  # No penalty - good timing to join
            
        else:
            return 0.8  # 20% penalty - normal timing
    
    def _analyze_context(self, message) -> float:
        """
        📊 CONVERSATION CONTEXT ANALYSIS
        Analyze message content and conversation relevance
        Returns penalty multiplier (0.1 = high penalty, 1.0 = no penalty)
        """
        channel_id = message.channel.id
        history = self.conversation_history.get(channel_id, [])
        
        current_msg = message.content.lower()
        current_author = message.author.id
        
        # 🎯 CONTENT ANALYSIS
        
        # 1. Direct questions to specific users
        directed_words = ['you ', 'your ', 'u ', 'ur ']
        if any(word in current_msg for word in directed_words):
            # Questions directed to "you" (likely to someone specific)
            if len(history) >= 2 and history[-2]['author_id'] != current_author:
                self.bot.log(f"👥 DIRECTED QUESTION detected: '{current_msg[:50]}...'", "WARNING")
                return 0.2  # 80% penalty - likely not for bot
        
        # 2. Personal conversation indicators
        personal_keywords = ['how are you', 'where are you', 'what are you doing', 'how you doing', 
                           'wassup', 'whats up', 'sup bro', 'hey man']
        if any(keyword in current_msg for keyword in personal_keywords):
            if len(history) >= 1 and history[-1]['author_id'] != current_author:
                self.bot.log(f"💬 PERSONAL CONVERSATION detected", "WARNING")
                return 0.3  # 70% penalty
        
        # 3. Continuation words (suggesting ongoing conversation)
        continuation_words = ['yes', 'no', 'yeah', 'nah', 'okay', 'ok', 'sure', 'alright', 
                            'right', 'exactly', 'true', 'lol', 'lmao', 'haha']
        if current_msg.strip().lower() in continuation_words:
            self.bot.log(f"🔄 CONTINUATION WORD detected: '{current_msg}'", "WARNING")
            return 0.1  # 90% penalty - clearly responding to someone
        
        # 4. Bot-relevant content (crypto, general topics)
        bot_keywords = ['crypto', 'bitcoin', 'market', 'trade', 'coin', 'bot', 'ai']
        if any(keyword in current_msg for keyword in bot_keywords):
            return 0.9  # 10% penalty - relevant to bot
        
        # 5. Questions vs statements
        if current_msg.endswith('?'):
            # Questions are more likely to include bot
            return 0.7  # 30% penalty
        else:
            # Statements less likely for bot
            return 0.5  # 50% penalty
    
    def cleanup_old_conversations(self):
        """Clean up old conversation data to save memory"""
        current_time = time.time()
        cleanup_threshold = 3600  # 1 hour
        
        for channel_id in list(self.conversation_history.keys()):
            # Remove old messages
            messages = self.conversation_history[channel_id]
            recent_messages = [
                msg for msg in messages 
                if (current_time - msg['timestamp']) <= cleanup_threshold
            ]
            
            if recent_messages:
                self.conversation_history[channel_id] = recent_messages
            else:
                del self.conversation_history[channel_id]
    
    def get_conversation_stats(self) -> dict:
        """Get conversation analysis statistics"""
        total_channels = len(self.conversation_history)
        total_messages = sum(len(msgs) for msgs in self.conversation_history.values())
        
        return {
            'tracked_channels': total_channels,
            'total_messages': total_messages,
            'rapid_threshold': self.rapid_response_threshold,
            'conversation_timeout': self.conversation_timeout
        }
    
    def _get_bot_silence_duration(self, channel_id) -> float:
        """Get duration since bot's last message in channel"""
        history = self.conversation_history.get(channel_id, [])
        current_time = time.time()
        
        # Find last bot message
        for msg in reversed(history):
            if msg['is_bot']:
                return current_time - msg['timestamp']
        
        # No bot message found = Very long silence (assume 2 hours)
        return 7200.0
