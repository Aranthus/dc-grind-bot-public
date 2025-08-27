import os
import json
import time
import random
import asyncio
import discord
import re
import traceback
from datetime import datetime, timedelta, time as dt_time
import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from activity_manager import ActivityManager
from chat_manager import ChatManager
from discord_activity import DiscordActivity
from prompts import get_prompt
from prompts.prompt_functions import PromptFunctions
from ai_providers import get_ai_provider
from discord import commands
from models import (
    BotConfigurationError, AIProviderError, ChannelNotFoundError,
    AISettings, MessageSettings, ChatSettings, ReplyChances,
    ActivitySettings, BotSettings, BotConfig,
    load_config, validate_bot_config
)
from core import MessageProcessor, BotInitializer, ConversationManager
from utils import BotHelpers
from handlers import EventHandler

# Constants
DEFAULT_BUFFER_TIMEOUT = 3.5
DEFAULT_TYPING_TIME = 2.0
DEFAULT_TEMPERATURE = 0.9
DEFAULT_ACTIVE_CHAT_LIMIT = 5
DEFAULT_CHUNK_SIZE = 2000
MIN_TYPING_DURATION = 1
MAX_TYPING_DURATION = 8
MIN_WPM = 40
MAX_WPM = 80
TYPING_VARIATION_MIN = 0.8
TYPING_VARIATION_MAX = 1.2

# Configuration classes moved to models/bot_config.py

class SelfBot(discord.Client):
    def __init__(self, bot_config: Union[Dict[str, Any], BotConfig]) -> None:
        """Initialize the bot"""
        # Store original config for memory manager
        self.original_config = bot_config if isinstance(bot_config, dict) else bot_config.__dict__
        
        # Convert dict to BotConfig if needed
        if isinstance(bot_config, dict):
            bot_config = BotConfig.from_dict(bot_config)
        
        # Validate configuration first
        validate_bot_config(bot_config)
        
        # Self-bot settings (no intents needed for self-bots)
        super().__init__(self_bot=True)
        
        # Initialize bot initializer and utilities first
        self.bot_initializer = BotInitializer(self)
        self.helpers = BotHelpers(self)  # Initialize helpers first for logging
        
        self.bot_initializer.setup_logging()
        self.bot_initializer.initialize_basic_config(bot_config)
        self.log(f"Initializing bot {self.bot_name}...", "WARNING")
        
        # Initialize all components using BotInitializer
        self.bot_initializer.initialize_managers(bot_config)
        self.bot_initializer.apply_activity_settings(bot_config)
        self.bot_initializer.initialize_message_settings(bot_config)
        self.bot_initializer.initialize_ai_settings(bot_config)
        self.bot_initializer.initialize_ai_provider(bot_config)
        self.bot_initializer.initialize_chat_settings(bot_config)
        self.bot_initializer.initialize_reply_settings(bot_config)
        
        # Initialize message processor, event handler, and conversation manager
        self.message_processor = MessageProcessor(self)
        self.event_handler = EventHandler(self)
        self.conversation_manager = ConversationManager(self)
        
        # Initialize memory manager for context-aware conversations
        # Use original config data for memory manager
        self.bot_initializer.initialize_memory_manager(self.original_config)
        
        # Initialize GIF manager for enhanced conversation
        self.bot_initializer.initialize_gif_manager(self.original_config)
        
        # Initialize voice manager for periodic voice activity
        self.bot_initializer.initialize_voice_manager(self.original_config)
        
        # Initialize admin manager for admin detection and silence
        self.bot_initializer.initialize_admin_manager(self.original_config)
        
        # Initialize server knowledge manager for channel direction
        self.bot_initializer.initialize_server_knowledge_manager(self.original_config)


    def log(self, message: str, level: str = "WARNING") -> None:
        """Log message - delegated to BotHelpers"""
        return self.helpers.log(message, level)
    
    async def process_message(self, message, content=None):
        """Process a received message - delegated to MessageProcessor"""
        return await self.message_processor.process_message(message, content)
    
    async def get_ai_response(self, user, message_content):
        """Get response from AI provider - delegated to MessageProcessor"""
        return await self.message_processor.get_ai_response(user, message_content)
    
    def clean_message(self, message):
        """Clean message content - delegated to MessageProcessor"""
        return self.message_processor.clean_message(message)
    
    def split_into_chunks(self, text, chunk_size=DEFAULT_CHUNK_SIZE):
        """Split text into chunks - delegated to MessageProcessor"""
        return self.message_processor.split_into_chunks(text, chunk_size)
    
    def combine_messages(self, messages):
        """Combine multiple messages into one - delegated to MessageProcessor"""
        return self.message_processor.combine_messages(messages)




    async def delayed_process(self, user_id):
        """Process buffer after waiting for a specified time"""
        await asyncio.sleep(self.buffer_timeout)
        await self.process_message_buffer(user_id)

    async def process_message_buffer(self, user_id):
        """Process message buffer for a user - delegated to MessageProcessor"""
        return await self.message_processor.process_message_buffer(user_id)

    async def setup_hook(self):
        """Bot startup settings"""
        try:
            # Set bot name from Discord username
            self.bot_name = self.user.name
            self.log(f"Bot name set to: {self.bot_name}", "WARNING")
            
            # Cancel existing tasks if they exist
            if hasattr(self, 'bg_task') and not self.bg_task.done():
                self.bg_task.cancel()
            
            # Start background tasks
            self.bg_task = self.loop.create_task(self.check_channel_activity())
            self.log("Background tasks started", "WARNING")
            
            # Initialize project manager for project-specific context
            await self.bot_initializer._init_project_manager()
            
            # Start Discord activity manager
            self.discord_activity.start_status_check()
            
        except Exception as e:
            self.log(f"Error in setup hook: {str(e)}", "WARNING")
            self.log(f"Error details:\n{traceback.format_exc()}", "WARNING")

    async def shutdown(self):
        """Shutdown the bot completely"""
        try:
            self.log("Starting bot shutdown...", "WARNING")
            
            # Cancel all background tasks
            if hasattr(self, 'bg_task'):
                self.bg_task.cancel()
            
            # Close Discord connection
            await self.close()
            
            # Stop the event loop
            self.loop.stop()
            
            self.log("Bot shutdown complete", "WARNING")
            
        except Exception as e:
            self.log(f"Error during shutdown: {str(e)}", "WARNING")
            self.log(f"Error details:\n{traceback.format_exc()}", "WARNING")

    async def close(self):
        """Properly close the bot"""
        try:
            # Cancel background tasks
            if hasattr(self, 'bg_task'):
                self.bg_task.cancel()
            
            # Cleanup AI provider
            if hasattr(self, 'ai_provider') and self.ai_provider:
                try:
                    await self.ai_provider.cleanup()
                except Exception as e:
                    self.log(f"Error cleaning up AI provider: {e}", "WARNING")
            
            # Cleanup GIF manager
            if hasattr(self, 'message_processor') and hasattr(self.message_processor, 'gif_manager'):
                if self.message_processor.gif_manager:
                    await self.message_processor.gif_manager.cleanup()
            
            # Cleanup voice manager
            if hasattr(self, 'voice_manager') and self.voice_manager:
                await self.voice_manager.stop_voice_activity()
            
            # Close Discord connection
            await super().close()
            
            self.log("Bot shutdown complete", "WARNING")
            
        except Exception as e:
            self.log(f"Error during shutdown: {str(e)}", "WARNING")
            self.log(f"Error details:\n{traceback.format_exc()}", "WARNING")

    async def check_channel_activity(self):
        """Check channel activity and start conversation if necessary - delegated to ConversationManager"""
        await self.conversation_manager.check_channel_activity()

    async def on_ready(self):
        """Bot is ready - delegated to EventHandler"""
        await self.event_handler.handle_ready()

    async def on_message(self, message):
        """Handle incoming messages - delegated to EventHandler"""
        await self.event_handler.handle_message(message)

    async def start_conversation(self, channel):
        """Start a new conversation in a channel - delegated to ConversationManager"""
        await self.conversation_manager.start_conversation(channel)

    async def update_user_activity(self, user, message_content):
        """Update user activity and get AI response"""
        try:
            self.logger.info(f"[DEBUG] Waiting for AI response...")
            response = await self.get_ai_response(user, message_content)
            return response
        except Exception as e:
            self.logger.error(f"Error updating user activity: {str(e)}")
            return None

    def get_user_name(self, user_id):
        """Get username from user ID - delegated to BotHelpers"""
        return self.helpers.get_user_name(user_id)

    def is_running(self):
        """Check if the bot is currently running - delegated to BotHelpers"""
        return self.helpers.is_running()

    def update_settings(self, reply_chances=None, buffer_timeout=None, typing_time=None, 
                       edit_wait_min=None, edit_wait_max=None, temperature=None):
        """Update bot settings while running - delegated to BotHelpers"""
        return self.helpers.update_settings(
            reply_chances=reply_chances,
            buffer_timeout=buffer_timeout,
            typing_time=typing_time,
            edit_wait_min=edit_wait_min,
            edit_wait_max=edit_wait_max,
            temperature=temperature
        )

    def convert_mentions_to_names(self, message):
        """Convert all types of mentions to readable names - delegated to BotHelpers"""
        return self.helpers.convert_mentions_to_names(message)

    def dispatch(self, event, *args, **kwargs):
        """Override to prevent event logging"""
        if event in ['socket_raw_receive', 'socket_response', 'typing']:
            return  # Bu eventleri tamamen yok say
        super().dispatch(event, *args, **kwargs)

    async def on_socket_response(self, msg):
        """Override to prevent socket response logging - delegated to EventHandler"""
        self.event_handler.handle_socket_response(msg)

    async def send_message(self, message, channel):
        """Send a message to a channel - delegated to MessageProcessor"""
        return await self.message_processor.send_message(message, channel)

    def calculate_typing_duration(self, message):
        """Calculate realistic typing duration - delegated to MessageProcessor"""
        return self.message_processor.calculate_typing_duration(message)

    def is_time_between(self, current_time, start_time, end_time):
        """Check if current time is between start and end time - delegated to BotHelpers"""
        return self.helpers.is_time_between(current_time, start_time, end_time)

async def main():
    """Main function to run the bot"""
    try:
        import sys
        import os
        
        if len(sys.argv) != 2:
            print("Usage: python discord_selfbot.py <config_name>")
            print("Example: python discord_selfbot.py config1")
            sys.exit(1)
        
        config_name = sys.argv[1]
        config_path = os.path.join("users", f"{config_name}.json")
        
        if not os.path.exists(config_path):
            print(f"Error: Config file {config_path} not found!")
            sys.exit(1)
        
        try:
            # Load the config file
            with open(config_path, "r", encoding="utf-8") as f:
                bot_config = json.load(f)
            
            # Create and run the bot
            client = SelfBot(bot_config)
            await client.start(bot_config['discord_token'])
            
        except BotConfigurationError as e:
            print(f"❌ Configuration Error: {str(e)}")
            print("Please check your configuration file and try again.")
            sys.exit(1)
        except AIProviderError as e:
            print(f"❌ AI Provider Error: {str(e)}")
            print("Please check your API keys and try again.")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in config file: {str(e)}")
            sys.exit(1)
        except FileNotFoundError:
            print(f"❌ Config file not found: {config_path}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            sys.exit(1)
            
    except Exception as e:
        print(f"Main error: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())