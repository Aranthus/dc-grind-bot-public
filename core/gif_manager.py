"""
GIF Manager - Tenor API Integration for Discord Self-Bot
Handles GIF search and embedding for natural conversation enhancement
"""

import re
import time
import aiohttp
import asyncio
from typing import Optional, Dict, Any
import logging

class GifManager:
    """Manages GIF search and integration using Tenor API"""
    
    def __init__(self, bot, tenor_api_key: str):
        self.bot = bot
        self.tenor_api_key = tenor_api_key
        self.tenor_base_url = "https://tenor.googleapis.com/v2"
        self.session: Optional[aiohttp.ClientSession] = None
        self.gif_cache: Dict[str, str] = {}  # Simple cache for frequent searches
        self.max_cache_size = 50
        
        # 🎯 GIF FREQUENCY CONTROL
        self.gif_usage_tracking = {}  # channel_id: [timestamps]
        self.max_gifs_per_timeframe = 2  # Max 2 GIFs
        self.gif_timeframe = 10800  # In 3 hours (10800 seconds)
        self.gif_cooldown_per_channel = 600  # 10 minutes between GIFs in same channel
        
        # Common GIF search patterns
        self.common_gifs = {
            'happy': ['happy', 'smile', 'joy'],
            'sad': ['sad', 'crying', 'disappointed'], 
            'laugh': ['laughing', 'lol', 'haha'],
            'love': ['love', 'heart', 'romance'],
            'angry': ['angry', 'mad', 'furious'],
            'surprised': ['surprised', 'shocked', 'wow'],
            'thinking': ['thinking', 'hmm', 'confused'],
            'celebration': ['celebration', 'party', 'congrats'],
            'good morning': ['good morning', 'morning', 'coffee'],
            'good night': ['good night', 'sleep', 'tired'],
            'crypto': ['crypto', 'bitcoin', 'money'],
            'moon': ['moon', 'rocket', 'to the moon'],
            'diamond hands': ['diamond hands', 'hodl', 'strong'],
            'rekt': ['rekt', 'crash', 'loss']
        }
    
    async def initialize(self):
        """Initialize aiohttp session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            self.bot.log("🎬 GIF Manager initialized with Tenor API", "INFO")
    
    async def cleanup(self):
        """Cleanup aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def extract_gif_commands(self, text: str) -> list:
        """Extract GIF commands from message text"""
        pattern = r'\[GIF:([^\]]+)\]'
        matches = re.findall(pattern, text, re.IGNORECASE)
        return matches
    
    def has_gif_command(self, text: str) -> bool:
        return bool(self.extract_gif_commands(text))
    
    def _can_send_gif(self, channel_id: int) -> bool:
        """Check if bot can send GIF based on frequency limits"""
        current_time = time.time()
        
        # Initialize tracking for channel if not exists
        if channel_id not in self.gif_usage_tracking:
            self.gif_usage_tracking[channel_id] = []
        
        # Clean old timestamps (older than timeframe)
        cutoff_time = current_time - self.gif_timeframe
        self.gif_usage_tracking[channel_id] = [
            ts for ts in self.gif_usage_tracking[channel_id] 
            if ts > cutoff_time
        ]
        
        # Check recent GIF count
        recent_gifs = len(self.gif_usage_tracking[channel_id])
        if recent_gifs >= self.max_gifs_per_timeframe:
            self.bot.log(f"🎬 GIF limit: {recent_gifs}/{self.max_gifs_per_timeframe} in last {self.gif_timeframe/60}min", "DEBUG")
            return False
        
        # Check cooldown between GIFs
        if self.gif_usage_tracking[channel_id]:
            last_gif_time = max(self.gif_usage_tracking[channel_id])
            time_since_last = current_time - last_gif_time
            if time_since_last < self.gif_cooldown_per_channel:
                self.bot.log(f"🎬 GIF cooldown: {time_since_last:.0f}s < {self.gif_cooldown_per_channel}s", "DEBUG")
                return False
        
        return True
    
    def _record_gif_usage(self, channel_id: int):
        """Record that a GIF was sent in this channel"""
        current_time = time.time()
        
        if channel_id not in self.gif_usage_tracking:
            self.gif_usage_tracking[channel_id] = []
        
        self.gif_usage_tracking[channel_id].append(current_time)
        self.bot.log(f"🎬 GIF usage recorded for channel {channel_id}", "DEBUG")
    
    def _remove_gif_commands(self, text: str) -> str:
        """Remove all GIF commands from text but keep the rest"""
        pattern = r'\[GIF:[^\]]+\]'
        cleaned_text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        # Clean up multiple spaces
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        return cleaned_text.strip()
    
    async def process_gif_message(self, text: str, channel_id: int = None) -> str:
        """Process message and replace GIF commands with actual GIF URLs"""
        if not self.has_gif_command(text):
            return text
        
        # 🎯 CHECK GIF FREQUENCY LIMITS
        if channel_id and not self._can_send_gif(channel_id):
            self.bot.log("🎬 GIF limit reached, removing GIF commands", "WARNING")
            # Remove all GIF commands but keep the text
            processed_text = self._remove_gif_commands(text)
            return processed_text.strip()
        
        processed_text = text
        gif_commands = self.extract_gif_commands(text)
        
        for command in gif_commands:
            gif_url = await self.search_gif(command.strip())
            
            if gif_url:
                # Replace the command with the GIF URL
                pattern = rf'\[GIF:{re.escape(command)}\]'
                processed_text = re.sub(pattern, gif_url, processed_text, flags=re.IGNORECASE)
                self.bot.log(f"🎬 GIF found for '{command}': {gif_url[:50]}...", "INFO")
                # Record GIF usage for frequency tracking
                if channel_id:
                    self._record_gif_usage(channel_id)
            else:
                # Remove the command if no GIF found
                pattern = rf'\[GIF:{re.escape(command)}\]'
                processed_text = re.sub(pattern, '', processed_text, flags=re.IGNORECASE)
                self.bot.log(f"🎬 No GIF found for '{command}', removing command", "WARNING")
        
        return processed_text.strip()
    
    async def search_gif(self, query: str) -> Optional[str]:
        """Search for GIF using Tenor API"""
        try:
            # Check cache first
            cache_key = query.lower().strip()
            if cache_key in self.gif_cache:
                self.bot.log(f"🎬 GIF cache hit for '{query}'", "DEBUG")
                return self.gif_cache[cache_key]
            
            if not self.session:
                await self.initialize()
            
            # Enhance query with common alternatives
            enhanced_query = self._enhance_query(query)
            
            # Build Tenor API URL (v2 format)
            params = {
                'q': enhanced_query,
                'key': self.tenor_api_key,
                'limit': 5,  # Get multiple options
                'client_key': 'discord_selfbot',  # Client identifier
                'media_filter': 'gif'  # Only GIFs
            }
            
            url = f"{self.tenor_base_url}/search"
            
            self.bot.log(f"🎬 Searching Tenor for: '{enhanced_query}'", "DEBUG")
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('results'):
                        # Get the first result's GIF URL (v2 API format)
                        gif_data = data['results'][0]
                        # Try v2 format first, fallback to v1 format
                        if 'url' in gif_data:
                            gif_url = gif_data['url']  # v2 format
                        elif 'media' in gif_data:
                            gif_url = gif_data['media'][0]['gif']['url']  # v1 format
                        else:
                            self.bot.log(f"🎬 Unknown response format: {gif_data.keys()}", "ERROR")
                            return None
                        
                        # Cache the result
                        self._cache_gif(cache_key, gif_url)
                        
                        return gif_url
                    else:
                        self.bot.log(f"🎬 No GIF results for '{query}'", "WARNING")
                        return None
                else:
                    # Enhanced error logging
                    error_text = await response.text()
                    self.bot.log(f"🎬 Tenor API error {response.status}: {error_text[:200]}", "ERROR")
                    self.bot.log(f"🎬 Request URL: {url}", "DEBUG")
                    self.bot.log(f"🎬 Request params: {params}", "DEBUG")
                    return None
                    
        except Exception as e:
            self.bot.log(f"🎬 GIF search error: {str(e)}", "ERROR")
            return None
    
    def _enhance_query(self, query: str) -> str:
        """Enhance search query with common alternatives"""
        query_lower = query.lower().strip()
        
        # Check if query matches common patterns
        for pattern, alternatives in self.common_gifs.items():
            if pattern in query_lower or query_lower in alternatives:
                return alternatives[0]  # Use the primary term
        
        return query
    
    def _cache_gif(self, query: str, gif_url: str):
        """Cache GIF URL with size limit"""
        if len(self.gif_cache) >= self.max_cache_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self.gif_cache))
            del self.gif_cache[oldest_key]
        
        self.gif_cache[query] = gif_url
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'cache_size': len(self.gif_cache),
            'max_cache_size': self.max_cache_size,
            'cached_queries': list(self.gif_cache.keys())
        }
    
    def get_frequency_stats(self) -> Dict[str, Any]:
        """Get GIF frequency statistics"""
        current_time = time.time()
        stats = {
            'max_gifs_per_timeframe': self.max_gifs_per_timeframe,
            'timeframe_minutes': self.gif_timeframe / 60,
            'cooldown_minutes': self.gif_cooldown_per_channel / 60,
            'channels': {}
        }
        
        for channel_id, timestamps in self.gif_usage_tracking.items():
            # Clean old timestamps
            recent_timestamps = [ts for ts in timestamps if ts > current_time - self.gif_timeframe]
            stats['channels'][channel_id] = {
                'recent_gifs': len(recent_timestamps),
                'can_send_gif': len(recent_timestamps) < self.max_gifs_per_timeframe,
                'last_gif_ago_minutes': (current_time - max(timestamps)) / 60 if timestamps else None
            }
        
        return stats
    
    def clear_cache(self):
        """Clear GIF cache"""
        self.gif_cache.clear()
        self.bot.log("🎬 GIF cache cleared", "INFO")
