"""
Conversation Management Core Module

This module handles conversation initiation, channel activity monitoring,
and conversation flow management for the Discord bot.
"""

import time
import random
import asyncio
from typing import TYPE_CHECKING, List, Dict

if TYPE_CHECKING:
    from discord_selfbot import SelfBot


class ConversationManager:
    """Manages conversation flow and channel activity monitoring"""
    
    def __init__(self, bot: 'SelfBot'):
        self.bot = bot
    
    async def start_conversation(self, channel) -> None:
        """Start a new conversation in a channel"""
        try:
            # Select random greeting
            greeting = random.choice(self.bot.greetings)
            
            # Show typing effect
            async with channel.typing():
                # Show typing indicator for configured time
                await asyncio.sleep(self.bot.typing_time)
            
            # Send message
            await channel.send(greeting)
            
            # Log
            self.bot.log(f"Started conversation in {channel.name} with: {greeting}", "WARNING")
                
        except Exception as e:
            self.bot.log(f"Error starting conversation: {str(e)}", "ERROR")
    
    async def check_channel_activity(self) -> None:
        """Check channel activity and start conversation if necessary"""
        while True:  # Continuous monitoring loop
            try:
                current_time = time.time()
                self.bot.log("Checking channel activity...", "WARNING")
                
                for channel_id in self.bot.channel_ids:
                    if not channel_id:  # Skip empty channel IDs
                        continue
                        
                    channel = self.bot.get_channel(int(channel_id))
                    if not channel:
                        self.bot.log(f"Channel not found: {channel_id}", "WARNING")
                        continue
                    
                    self.bot.log(f"Checking channel: {channel.name} ({channel_id})", "WARNING")
                    
                    # Get last chat time for this channel, check real channel history if needed
                    last_chat_time = self.bot.last_chat_times.get(channel_id, 0)
                    
                    # If no recorded time (bot just started), check actual channel history
                    if last_chat_time == 0:
                        last_chat_time = await self._get_last_message_time(channel)
                        self.bot.last_chat_times[channel_id] = last_chat_time
                    
                    # Calculate time since last chat
                    time_since_last_chat = current_time - last_chat_time
                    
                    self.bot.log(f"Time since last chat: {time_since_last_chat/60:.1f} minutes (cooldown: {self.bot.chat_cooldown/60:.1f} min)", "WARNING")
                    
                    # Check if bot should stay silent due to admin activity
                    if hasattr(self.bot, 'admin_manager') and self.bot.admin_manager:
                        if self.bot.admin_manager.should_bot_stay_silent():
                            # Bot is in admin silence mode - skip conversation starting
                            continue
                    
                    # Check if enough time has passed (minimum 1 hour of silence before greeting)
                    if time_since_last_chat >= self.bot.chat_cooldown:
                        self.bot.log(f"Starting conversation in channel: {channel.name}", "WARNING")
                        # Start new conversation
                        await self.start_conversation(channel)
                        # Update last chat time
                        self.bot.last_chat_times[channel_id] = current_time
                
                # Check every 15 seconds (reduced frequency to avoid rate limits)
                await asyncio.sleep(15)
                    
            except Exception as e:
                self.bot.log(f"Channel activity check error: {str(e)}", "WARNING")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _get_last_message_time(self, channel) -> float:
        """Get timestamp of the last message in channel from history"""
        try:
            # Fetch last few messages from channel
            async for message in channel.history(limit=10):
                # Return timestamp of most recent message
                return message.created_at.timestamp()
            
            # If no messages found, return current time minus cooldown (so bot won't start conversation)
            import time
            return time.time() - (self.bot.chat_cooldown / 2)
            
        except Exception as e:
            self.bot.log(f"Error getting last message time: {e}", "WARNING")
            # On error, assume recent activity to prevent spam
            import time
            return time.time() - 300  # 5 minutes ago
    
    def should_start_conversation(self, channel_id: str, current_time: float) -> bool:
        """Check if bot should start a conversation in the given channel"""
        try:
            # Get last chat time for this channel
            last_chat_time = self.bot.last_chat_times.get(channel_id, 0)
            
            # Calculate time since last chat
            time_since_last_chat = current_time - last_chat_time
            
            # Check if enough time has passed
            return time_since_last_chat >= self.bot.chat_cooldown
            
        except Exception as e:
            self.bot.log(f"Error checking conversation timing: {str(e)}", "ERROR")
            return False
    
    def update_last_chat_time(self, channel_id: str, current_time: float = None) -> None:
        """Update the last chat time for a channel"""
        try:
            if current_time is None:
                current_time = time.time()
            
            self.bot.last_chat_times[channel_id] = current_time
            self.bot.log(f"Updated last chat time for channel {channel_id}", "DEBUG")
            
        except Exception as e:
            self.bot.log(f"Error updating last chat time: {str(e)}", "ERROR")
    
    def get_conversation_state(self, channel_id: str) -> Dict:
        """Get conversation state for a channel"""
        try:
            return self.bot.conversation_states.get(channel_id, {
                'active': False,
                'last_message_time': 0,
                'message_count': 0,
                'participants': []
            })
        except Exception as e:
            self.bot.log(f"Error getting conversation state: {str(e)}", "ERROR")
            return {}
    
    def update_conversation_state(self, channel_id: str, state_updates: Dict) -> None:
        """Update conversation state for a channel"""
        try:
            if channel_id not in self.bot.conversation_states:
                self.bot.conversation_states[channel_id] = {
                    'active': False,
                    'last_message_time': 0,
                    'message_count': 0,
                    'participants': []
                }
            
            self.bot.conversation_states[channel_id].update(state_updates)
            self.bot.log(f"Updated conversation state for channel {channel_id}", "DEBUG")
            
        except Exception as e:
            self.bot.log(f"Error updating conversation state: {str(e)}", "ERROR")
    
    def get_active_conversations(self) -> List[str]:
        """Get list of channels with active conversations"""
        try:
            active_channels = []
            for channel_id, state in self.bot.conversation_states.items():
                if state.get('active', False):
                    active_channels.append(channel_id)
            return active_channels
        except Exception as e:
            self.bot.log(f"Error getting active conversations: {str(e)}", "ERROR")
            return []
