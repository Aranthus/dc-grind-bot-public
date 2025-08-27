"""
Voice Channel Manager - Discord Self-Bot Voice Activity
Handles periodic voice channel joining/leaving for natural human-like behavior
"""

import asyncio
import random
import time
from typing import Dict, List, Optional, TYPE_CHECKING
import discord

if TYPE_CHECKING:
    from discord_selfbot import SelfBot

class VoiceManager:
    """Manages voice channel joining/leaving activities"""
    
    def __init__(self, bot: 'SelfBot'):
        self.bot = bot
        self.voice_config = {
            'join_interval': 7200,      # 2 hours (7200 seconds)
            'stay_duration': 600,       # 10 minutes (600 seconds)
            'enabled': True,            # Enable voice activity
            'random_delay': 1800,       # Up to 30min random delay
            'preferred_channels': [],   # Specific channels to prefer
            'avoid_channels': []        # Channels to avoid
        }
        
        # State tracking
        self.voice_client: Optional[discord.VoiceClient] = None
        self.current_voice_channel = None
        self.last_voice_activity = 0
        self.voice_leave_task: Optional[asyncio.Task] = None
        self.voice_schedule_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Statistics
        self.voice_stats = {
            'total_joins': 0,
            'total_time_spent': 0,
            'channels_visited': set(),
            'last_join_time': None,
            'last_leave_time': None
        }
    
    async def start_voice_activity(self):
        """Start the voice activity scheduler"""
        if self.is_running:
            return
        
        self.is_running = True
        self.voice_schedule_task = asyncio.create_task(self._voice_activity_loop())
        self.bot.log("🎤 Voice Manager started - periodic voice activity enabled", "INFO")
    
    async def stop_voice_activity(self):
        """Stop voice activity and cleanup"""
        self.is_running = False
        
        # Cancel scheduled tasks
        if self.voice_schedule_task:
            self.voice_schedule_task.cancel()
        
        if self.voice_leave_task:
            self.voice_leave_task.cancel()
        
        # Leave current voice channel
        await self._leave_voice_channel()
        
        self.bot.log("🎤 Voice Manager stopped", "INFO")
    
    async def _voice_activity_loop(self):
        """Main loop for voice activity scheduling"""
        while self.is_running:
            try:
                # Calculate next join time
                base_interval = self.voice_config['join_interval']
                random_delay = random.randint(0, self.voice_config['random_delay'])
                next_join_delay = base_interval + random_delay
                
                self.bot.log(f"🎤 Next voice activity in {next_join_delay/60:.0f} minutes", "INFO")
                
                # Wait for the scheduled time
                await asyncio.sleep(next_join_delay)
                
                # Check if bot should be active
                if not self._should_be_active():
                    self.bot.log("🎤 Bot inactive, skipping voice activity", "DEBUG")
                    continue
                
                # Join a voice channel
                await self._join_random_voice_channel()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.bot.log(f"🎤 Voice activity loop error: {str(e)}", "ERROR")
                await asyncio.sleep(300)  # Wait 5 minutes before retry
    
    async def _join_random_voice_channel(self):
        """Join a random available voice channel"""
        try:
            # Get available voice channels
            voice_channels = self._get_available_voice_channels()
            
            if not voice_channels:
                self.bot.log("🎤 No available voice channels found", "WARNING")
                return
            
            # Select channel based on preferences
            selected_channel = self._select_voice_channel(voice_channels)
            if not selected_channel:
                return
            
            self.bot.log(f"🎤 Joining voice channel: {selected_channel.name}", "INFO")
            
            # Join the voice channel
            try:
                self.voice_client = await selected_channel.connect()
                self.current_voice_channel = selected_channel
                self.last_voice_activity = time.time()
                
                # Update statistics
                self.voice_stats['total_joins'] += 1
                self.voice_stats['channels_visited'].add(selected_channel.id)
                self.voice_stats['last_join_time'] = time.time()
                
                # Schedule leave after stay duration
                stay_time = self.voice_config['stay_duration']
                random_stay_variation = random.randint(-120, 300)  # -2min to +5min variation
                actual_stay_time = max(300, stay_time + random_stay_variation)  # Minimum 5 minutes
                
                self.bot.log(f"🎤 Will leave voice channel in {actual_stay_time/60:.1f} minutes", "INFO")
                self.voice_leave_task = asyncio.create_task(self._schedule_voice_leave(actual_stay_time))
                
            except discord.ClientException as e:
                self.bot.log(f"🎤 Failed to join voice channel: {str(e)}", "ERROR")
            
        except Exception as e:
            self.bot.log(f"🎤 Error joining voice channel: {str(e)}", "ERROR")
    
    async def _schedule_voice_leave(self, delay: int):
        """Schedule leaving the voice channel after delay"""
        try:
            await asyncio.sleep(delay)
            await self._leave_voice_channel()
        except asyncio.CancelledError:
            pass
    
    async def _leave_voice_channel(self):
        """Leave current voice channel"""
        if self.voice_client and self.voice_client.is_connected():
            try:
                channel_name = self.current_voice_channel.name if self.current_voice_channel else "Unknown"
                self.bot.log(f"🎤 Leaving voice channel: {channel_name}", "INFO")
                
                # Calculate time spent
                if self.voice_stats['last_join_time']:
                    time_spent = time.time() - self.voice_stats['last_join_time']
                    self.voice_stats['total_time_spent'] += time_spent
                
                await self.voice_client.disconnect()
                self.voice_stats['last_leave_time'] = time.time()
                
            except Exception as e:
                self.bot.log(f"🎤 Error leaving voice channel: {str(e)}", "ERROR")
            finally:
                self.voice_client = None
                self.current_voice_channel = None
                if self.voice_leave_task:
                    self.voice_leave_task = None
    
    def _get_available_voice_channels(self) -> List[discord.VoiceChannel]:
        """Get list of available voice channels"""
        channels = []
        
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                # Skip if in avoid list
                if channel.id in self.voice_config['avoid_channels']:
                    continue
                
                # Check if bot has permissions
                if not channel.permissions_for(guild.me).connect:
                    continue
                
                # Skip if channel is full
                if channel.user_limit and len(channel.members) >= channel.user_limit:
                    continue
                
                channels.append(channel)
        
        return channels
    
    def _select_voice_channel(self, channels: List[discord.VoiceChannel]) -> Optional[discord.VoiceChannel]:
        """Select best voice channel to join"""
        if not channels:
            return None
        
        # Prefer channels with people (more natural)
        channels_with_people = [ch for ch in channels if len(ch.members) > 0]
        channels_empty = [ch for ch in channels if len(ch.members) == 0]
        
        # Prefer channels with 1-3 people (not too crowded, not empty)
        ideal_channels = [ch for ch in channels_with_people if 1 <= len(ch.members) <= 3]
        
        # Selection priority:
        # 1. Preferred channels with ideal member count
        preferred_ideal = [ch for ch in ideal_channels if ch.id in self.voice_config['preferred_channels']]
        if preferred_ideal:
            return random.choice(preferred_ideal)
        
        # 2. Any ideal channels
        if ideal_channels:
            return random.choice(ideal_channels)
        
        # 3. Preferred channels with people
        preferred_with_people = [ch for ch in channels_with_people if ch.id in self.voice_config['preferred_channels']]
        if preferred_with_people:
            return random.choice(preferred_with_people)
        
        # 4. Any channel with people
        if channels_with_people:
            return random.choice(channels_with_people)
        
        # 5. Empty channels as last resort
        if channels_empty:
            return random.choice(channels_empty)
        
        return None
    
    def _should_be_active(self) -> bool:
        """Check if bot should be active for voice joining"""
        if not self.voice_config['enabled']:
            return False
        
        # Check if bot is in active hours
        if hasattr(self.bot, 'activity_manager'):
            return self.bot.activity_manager.should_be_online()
        
        return True
    
    def update_voice_config(self, config: Dict):
        """Update voice configuration"""
        self.voice_config.update(config)
        self.bot.log(f"🎤 Voice config updated: {config}", "INFO")
    
    def get_voice_stats(self) -> Dict:
        """Get voice activity statistics"""
        current_time = time.time()
        
        return {
            'enabled': self.voice_config['enabled'],
            'currently_in_voice': self.voice_client is not None,
            'current_channel': self.current_voice_channel.name if self.current_voice_channel else None,
            'total_joins': self.voice_stats['total_joins'],
            'total_time_hours': self.voice_stats['total_time_spent'] / 3600,
            'channels_visited_count': len(self.voice_stats['channels_visited']),
            'last_activity_ago_minutes': (current_time - self.last_voice_activity) / 60 if self.last_voice_activity else None,
            'next_activity_in_minutes': self._get_next_activity_time(),
            'config': self.voice_config
        }
    
    def _get_next_activity_time(self) -> Optional[float]:
        """Calculate minutes until next voice activity"""
        if not self.is_running or not self.last_voice_activity:
            return None
        
        next_time = self.last_voice_activity + self.voice_config['join_interval']
        current_time = time.time()
        
        if next_time > current_time:
            return (next_time - current_time) / 60
        
        return 0  # Should join soon
    
    async def force_voice_activity(self):
        """Manually trigger voice activity (for testing)"""
        if self.voice_client:
            self.bot.log("🎤 Already in voice channel, leaving first", "WARNING")
            await self._leave_voice_channel()
            await asyncio.sleep(2)
        
        await self._join_random_voice_channel()
    
    async def force_voice_leave(self):
        """Manually leave voice channel"""
        await self._leave_voice_channel()
