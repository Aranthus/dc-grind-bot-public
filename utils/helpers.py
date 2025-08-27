"""
Bot Helper Utilities

This module contains utility functions for various bot operations including
time management, message formatting, user operations, and general helpers.
"""

import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from discord_selfbot import SelfBot


class BotHelpers:
    """Utility functions for bot operations"""
    
    def __init__(self, bot: 'SelfBot'):
        self.bot = bot
    
    def log(self, message: str, level: str = "WARNING") -> None:
        """Log a message with the specified level"""
        try:
            if level.upper() == "DEBUG":
                self.bot.logger.debug(message)
            elif level.upper() == "INFO":
                self.bot.logger.info(message)
            elif level.upper() == "WARNING":
                self.bot.logger.warning(message)
            elif level.upper() == "ERROR":
                self.bot.logger.error(message)
            elif level.upper() == "CRITICAL":
                self.bot.logger.critical(message)
            else:
                self.bot.logger.warning(message)
        except Exception as e:
            print(f"Log error: {str(e)} - Message: {message}")
    
    def get_user_name(self, user_id: int) -> str:
        """Get user display name by ID"""
        try:
            user = self.bot.get_user(user_id)
            return user.display_name if user else f"Unknown User ({user_id})"
        except Exception as e:
            self.log(f"Error getting user name for {user_id}: {str(e)}", "ERROR")
            return f"Unknown User ({user_id})"
    
    def is_running(self) -> bool:
        """Check if bot is running"""
        return not self.bot.is_closed()
    
    def convert_mentions_to_names(self, message) -> str:
        """Convert user mentions in message to readable names"""
        content = message.content
        
        # User mentions (@user)
        user_mention_pattern = r'<@!?(\d+)>'
        user_mentions = re.findall(user_mention_pattern, content)
        
        for user_id in user_mentions:
            try:
                user = self.bot.get_user(int(user_id))
                if user:
                    display_name = user.display_name if hasattr(user, 'display_name') else user.name
                    # Replace mention with readable name
                    content = re.sub(f'<@!?{user_id}>', f'@{display_name}', content)
                else:
                    # If user not found, replace with Unknown
                    content = re.sub(f'<@!?{user_id}>', f'@Unknown({user_id})', content)
            except Exception as e:
                self.log(f"Error converting mention {user_id}: {str(e)}", "WARNING")
                content = re.sub(f'<@!?{user_id}>', f'@Unknown({user_id})', content)
        
        # Role mentions (@role)
        role_mention_pattern = r'<@&(\d+)>'
        role_mentions = re.findall(role_mention_pattern, content)
        
        for role_id in role_mentions:
            try:
                # Get guild from message
                if hasattr(message, 'guild') and message.guild:
                    role = message.guild.get_role(int(role_id))
                    if role:
                        content = re.sub(f'<@&{role_id}>', f'@{role.name}', content)
                    else:
                        content = re.sub(f'<@&{role_id}>', f'@Unknown Role({role_id})', content)
                else:
                    content = re.sub(f'<@&{role_id}>', f'@Unknown Role({role_id})', content)
            except Exception as e:
                self.log(f"Error converting role mention {role_id}: {str(e)}", "WARNING")
                content = re.sub(f'<@&{role_id}>', f'@Unknown Role({role_id})', content)
        
        # Channel mentions (#channel)
        channel_mention_pattern = r'<#(\d+)>'
        channel_mentions = re.findall(channel_mention_pattern, content)
        
        for channel_id in channel_mentions:
            try:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    content = re.sub(f'<#{channel_id}>', f'#{channel.name}', content)
                else:
                    content = re.sub(f'<#{channel_id}>', f'#Unknown Channel({channel_id})', content)
            except Exception as e:
                self.log(f"Error converting channel mention {channel_id}: {str(e)}", "WARNING")
                content = re.sub(f'<#{channel_id}>', f'#Unknown Channel({channel_id})', content)
        
        return content
    
    def is_time_between(self, current_time: datetime, start_time: tuple, end_time: tuple) -> bool:
        """Check if current time is between start and end time"""
        try:
            start_hour, start_minute = start_time
            end_hour, end_minute = end_time
            
            current_hour = current_time.hour
            current_minute = current_time.minute
            
            # Convert to minutes for easier comparison
            current_minutes = current_hour * 60 + current_minute
            start_minutes = start_hour * 60 + start_minute
            end_minutes = end_hour * 60 + end_minute
            
            # Handle cases where end time is next day
            if end_minutes < start_minutes:
                # Time spans midnight
                return current_minutes >= start_minutes or current_minutes <= end_minutes
            else:
                # Normal time range
                return start_minutes <= current_minutes <= end_minutes
                
        except Exception as e:
            self.log(f"Error checking time range: {str(e)}", "ERROR")
            return True  # Default to always active if error
    
    def update_settings(self, reply_chances=None, buffer_timeout=None, typing_time=None, 
                       chat_cooldown=None, ai_provider=None, edit_wait_min=None, 
                       edit_wait_max=None, temperature=None, **kwargs) -> None:
        """Update bot settings dynamically"""
        try:
            if reply_chances:
                self.bot.reply_chances.update(reply_chances)
                self.log(f"Updated reply chances: {reply_chances}", "WARNING")
            
            if buffer_timeout:
                self.bot.buffer_timeout = buffer_timeout
                self.log(f"Updated buffer timeout: {buffer_timeout}", "WARNING")
            
            if typing_time:
                self.bot.typing_time = typing_time
                self.log(f"Updated typing time: {typing_time}", "WARNING")
            
            if chat_cooldown:
                self.bot.chat_cooldown = chat_cooldown
                self.log(f"Updated chat cooldown: {chat_cooldown}", "WARNING")
            
            if edit_wait_min is not None:
                if hasattr(self.bot, 'edit_wait_time'):
                    self.bot.edit_wait_time['min'] = float(edit_wait_min)
                    self.log(f"Updated edit wait min: {edit_wait_min}", "WARNING")
            
            if edit_wait_max is not None:
                if hasattr(self.bot, 'edit_wait_time'):
                    self.bot.edit_wait_time['max'] = float(edit_wait_max)
                    self.log(f"Updated edit wait max: {edit_wait_max}", "WARNING")
            
            if temperature is not None:
                self.bot.temperature = float(temperature)
                self.log(f"Updated temperature: {temperature}", "WARNING")
                # Update AI provider temperature if supported
                if hasattr(self.bot.ai_provider, 'set_temperature'):
                    self.bot.ai_provider.set_temperature(self.bot.temperature)
            
            if ai_provider:
                # This would require reinitializing the AI provider
                self.log(f"AI provider update requested: {ai_provider} (requires restart)", "WARNING")
            
            # Update any additional kwargs
            for key, value in kwargs.items():
                if hasattr(self.bot, key):
                    setattr(self.bot, key, value)
                    self.log(f"Updated {key}: {value}", "WARNING")
                else:
                    self.log(f"Unknown setting: {key}", "WARNING")
                    
        except Exception as e:
            self.log(f"Error updating settings: {str(e)}", "ERROR")
