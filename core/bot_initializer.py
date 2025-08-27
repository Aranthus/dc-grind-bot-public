"""
Bot Initialization Core Module

This module handles all bot initialization logic including configuration setup,
manager initialization, and component bootstrapping.
"""

import traceback
import logging
from typing import TYPE_CHECKING
from models import BotConfig
from activity_manager import ActivityManager
from chat_manager import ChatManager
from discord_activity import DiscordActivity
from ai_providers import get_ai_provider
from core.gif_manager import GifManager
from core.voice_manager import VoiceManager
from core.admin_manager import AdminManager
from core.server_knowledge_manager import ServerKnowledgeManager
from core.project_manager import ProjectManager

if TYPE_CHECKING:
    from discord_selfbot import SelfBot

# Constants
DEFAULT_ACTIVE_CHAT_LIMIT = 5


class BotInitializer:
    """Handles all bot initialization operations"""
    
    def __init__(self, bot: 'SelfBot'):
        self.bot = bot
    
    def setup_logging(self) -> None:
        """Setup logging configuration"""
        try:
            # Configure logging
            logging.basicConfig(
                level=logging.WARNING,  # DEBUG yerine WARNING kullanıyoruz
                format='%(asctime)s [%(levelname)s] %(message)s',
                handlers=[
                    logging.StreamHandler()
                ]
            )
            
            # Discord.py loglarını kapat
            discord_logger = logging.getLogger('discord')
            discord_logger.setLevel(logging.ERROR)  # Sadece hataları göster
            
            self.bot.logger = logging.getLogger(__name__)
            self.bot.logger.setLevel(logging.WARNING)  # DEBUG yerine WARNING kullanıyoruz
        except Exception as e:
            print(f"Logging error: {str(e)}")
    
    def initialize_basic_config(self, bot_config: BotConfig) -> None:
        """Initialize basic bot configuration"""
        self.bot.bot_config = bot_config
        self.bot.bot_id = bot_config.id
        self.bot.bot_name = bot_config.name
        self.bot.token = bot_config.discord_token
        self.bot.channel_ids = bot_config.channels
        self.bot.target_channels = []

    def initialize_managers(self, bot_config: BotConfig) -> None:
        """Initialize all manager instances"""
        # Convert BotConfig back to dict format for backward compatibility
        # This allows existing managers to work without modification
        config_dict = {
            'id': bot_config.id,
            'name': bot_config.name,
            'discord_token': bot_config.discord_token,
            'api_keys': bot_config.api_keys,
            'channels': bot_config.channels,
            'active': bot_config.active,
            'settings': {
                'ai_provider': bot_config.settings.ai_provider,
                'prompt_type': bot_config.settings.prompt_type,
                'greetings': bot_config.settings.greetings,
                'active_duration': bot_config.settings.activity_settings.active_duration,
                'afk_duration': bot_config.settings.activity_settings.afk_duration,
                'message_limit': bot_config.settings.activity_settings.message_limit,
                'ai_settings': bot_config.settings.ai_settings.__dict__,
                'chat_settings': bot_config.settings.chat_settings.__dict__,
                'reply_chances': bot_config.settings.reply_chances.__dict__
            },
            'message_settings': bot_config.message_settings.__dict__
        }
        
        self.bot.chat_manager = ChatManager(self.bot, config_dict)
        self.bot.activity_manager = ActivityManager(config_dict)
        self.bot.discord_activity = DiscordActivity(self.bot, config_dict)

    def apply_activity_settings(self, bot_config: BotConfig) -> None:
        """Apply activity-related settings from config"""
        activity_settings = bot_config.settings.activity_settings
        self.bot.online_hour_start = activity_settings.online_hour_start
        self.bot.online_minute_start = activity_settings.online_minute_start
        self.bot.online_hour_end = activity_settings.online_hour_end
        self.bot.online_minute_end = activity_settings.online_minute_end

    def initialize_message_settings(self, bot_config: BotConfig) -> None:
        """Initialize message-related settings"""
        message_settings = bot_config.message_settings
        self.bot.buffer_timeout = message_settings.buffer_timeout
        self.bot.typing_time = message_settings.typing_indicator_time
        self.bot.edit_wait_time = message_settings.edit_wait_time

    def initialize_ai_settings(self, bot_config: BotConfig) -> None:
        """Initialize AI-related settings"""
        ai_settings = bot_config.settings.ai_settings
        self.bot.temperature = ai_settings.temperature
        self.bot.active_chat_limit = DEFAULT_ACTIVE_CHAT_LIMIT  # Keep default for now
        self.bot.system_prompt = ""

    def initialize_ai_provider(self, bot_config: BotConfig) -> None:
        """Initialize AI provider"""
        provider = bot_config.settings.ai_provider
        self.bot.api_key = bot_config.api_keys.get(provider, '')
        
        self.bot.log("Setting up AI provider...", "WARNING")
        try:
            ai_settings_dict = bot_config.settings.ai_settings.__dict__
            masked_key = f"{self.bot.api_key[:4]}...{self.bot.api_key[-4:]}" if self.bot.api_key else "Not Set"
            self.bot.log(f"Using {provider.upper()} as AI provider with API key: {masked_key}", "WARNING")
            
            self.bot.ai_provider = get_ai_provider(provider, self.bot.api_key, ai_settings_dict)
            self.bot.log(f"Successfully initialized {provider.upper()} AI provider", "WARNING")
        except Exception as e:
            error_msg = f"Failed to initialize {provider.upper()} AI provider: {str(e)}"
            self.bot.log(error_msg, "ERROR")
            self.bot.log(f"Error details:\n{traceback.format_exc()}", "ERROR")
            from models import AIProviderError
            raise AIProviderError(error_msg) from e

    def initialize_chat_settings(self, bot_config: BotConfig) -> None:
        """Initialize chat-related settings"""
        chat_settings = bot_config.settings.chat_settings
        self.bot.chat_cooldown = chat_settings.chat_cooldown
        self.bot.min_silence_duration = chat_settings.min_silence_duration
        self.bot.max_silence_duration = chat_settings.max_silence_duration
        self.bot.waiting_response = {}  # Channels where we're waiting for response
        
        # Simple greeting messages
        self.bot.greetings = bot_config.settings.greetings
        
        # Message management
        self.bot.message_buffers = {}  # Message buffer for each user
        self.bot.buffer_timers = {}    # Timer tasks for buffer timeout
        
        # Initialize last chat times
        self.bot.last_chat_times = {channel_id: 0 for channel_id in self.bot.channel_ids if channel_id}

    def initialize_reply_settings(self, bot_config: BotConfig) -> None:
        """Initialize reply probability settings"""
        # Initialize message buffer for combining messages
        self.bot.message_buffer = {}  # user_id: [messages]
        self.bot.buffer_timers = {}   # user_id: timer_task
        
        # Initialize reply chances from config
        reply_chances = bot_config.settings.reply_chances
        self.bot.reply_chances = {
            'direct_mention': reply_chances.direct_mention,
            'indirect_mention': reply_chances.indirect_mention,
            'group_mention': reply_chances.group_mention,
            'reply_to_bot': reply_chances.reply_to_bot,
            'question': reply_chances.question,
            'normal_chat': reply_chances.normal_chat,
            'reply_chain': reply_chances.reply_chain
        }
        
        # Reply chain tracking
        self.bot.reply_chain_count = {}
        
        # Initialize context limits  
        self.bot.context_limits = {
            "conversation": 20,      # Number of conversation turns to remember
            "time_window": 3600,     # Time window for context (1 hour)
            "max_tokens": 4000       # Maximum tokens for context
        }
        
        # Initialize conversation states
        self.bot.conversation_states = {}  # Channel conversation tracking
        self.bot.user_contexts = {}        # User conversation contexts
        
        # Initialize delayed tasks for message processing
        self.bot.delayed_tasks = {}  # User delayed message tasks
    
    def initialize_memory_manager(self, config_dict):
        """Initialize memory manager for context-aware conversations"""
        try:
            supabase_config = config_dict.get('supabase', {})
            if not supabase_config:
                self.bot.log("No Supabase config found, memory disabled", "WARNING")
                return
            
            from core.memory_manager import MemoryManager
            
            memory_manager = MemoryManager(
                supabase_url=supabase_config.get('url'),
                supabase_key=supabase_config.get('anon_key')
            )
            
            # Connect to message processor
            if hasattr(self.bot, 'message_processor'):
                self.bot.message_processor.memory_manager = memory_manager
                self.bot.log("Memory manager initialized and connected", "INFO")
            else:
                self.bot.log("Message processor not found for memory manager", "WARNING")
                
        except Exception as e:
            self.bot.log(f"Failed to initialize memory manager: {e}", "ERROR")
    
    def initialize_gif_manager(self, config_dict):
        """Initialize GIF manager for enhanced conversation with Tenor API"""
        try:
            tenor_api_key = config_dict.get('api_keys', {}).get('tenor')
            if not tenor_api_key or tenor_api_key == 'YOUR_TENOR_API_KEY_HERE':
                self.bot.log("No Tenor API key found, GIF feature disabled", "WARNING")
                return
            
            gif_manager = GifManager(self.bot, tenor_api_key)
            # Initialize the GIF manager session
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, schedule the initialization
                    asyncio.create_task(gif_manager.initialize())
                else:
                    # If no loop running, run it synchronously
                    asyncio.run(gif_manager.initialize())
            except:
                # Fallback - initialize will happen on first use
                pass
            
            # Connect to message processor
            if hasattr(self.bot, 'message_processor'):
                self.bot.message_processor.gif_manager = gif_manager
                self.bot.log("🎬 GIF manager initialized and connected", "INFO")
            else:
                self.bot.log("Message processor not found for GIF manager", "WARNING")
                
        except Exception as e:
            self.bot.log(f"Failed to initialize GIF manager: {e}", "ERROR")
    
    def initialize_voice_manager(self, config_dict):
        """Initialize voice manager for periodic voice channel activity"""
        try:
            voice_settings = config_dict.get('settings', {}).get('voice_settings', {})
            if not voice_settings.get('enabled', False):
                self.bot.log("Voice activity disabled in config", "WARNING")
                return
            
            voice_manager = VoiceManager(self.bot)
            
            # Update voice config from settings
            voice_config = {
                'join_interval': voice_settings.get('join_interval_hours', 2) * 3600,
                'stay_duration': voice_settings.get('stay_duration_minutes', 10) * 60,
                'random_delay': voice_settings.get('random_delay_minutes', 30) * 60,
                'enabled': voice_settings.get('enabled', True),
                'preferred_channels': voice_settings.get('preferred_channels', []),
                'avoid_channels': voice_settings.get('avoid_channels', [])
            }
            
            voice_manager.update_voice_config(voice_config)
            
            # Store in bot
            self.bot.voice_manager = voice_manager
            self.bot.log("🎤 Voice manager initialized and configured", "INFO")
                
        except Exception as e:
            self.bot.log(f"Failed to initialize voice manager: {e}", "ERROR")
    
    def initialize_admin_manager(self, config_dict):
        """Initialize admin manager for admin detection and silence mode"""
        try:
            admin_settings = config_dict.get('settings', {}).get('admin_settings', {})
            if not admin_settings.get('enabled', False):
                self.bot.log("Admin detection disabled in config", "WARNING")
                return
            
            admin_manager = AdminManager(self.bot)
            admin_manager.update_admin_config(admin_settings)
            
            # Store in bot
            self.bot.admin_manager = admin_manager
            self.bot.log("👮‍♂️ Admin manager initialized and configured", "INFO")
                
        except Exception as e:
            self.bot.log(f"Failed to initialize admin manager: {e}", "ERROR")
    
    def initialize_server_knowledge_manager(self, config_dict):
        """Initialize server knowledge manager for channel direction"""
        try:
            knowledge_settings = config_dict.get('settings', {}).get('server_knowledge', {})
            if not knowledge_settings.get('enabled', False):
                self.bot.log("Server knowledge disabled in config", "WARNING")
                return
            
            knowledge_manager = ServerKnowledgeManager(self.bot)
            knowledge_manager.update_knowledge_config(knowledge_settings)
            
            # Store in bot
            self.bot.server_knowledge_manager = knowledge_manager
            self.bot.log("📚 Server knowledge manager initialized and configured", "INFO")
                
        except Exception as e:
            self.bot.log(f"Failed to initialize server knowledge manager: {e}", "ERROR")
    
    async def _init_project_manager(self):
        """Initialize project manager for project-specific context"""
        try:
            project_manager = ProjectManager(self.bot)
            success = await project_manager.initialize()
            
            if success:
                self.bot.project_manager = project_manager
                self.bot.log("🏢 Project manager initialized successfully", "INFO")
            else:
                self.bot.log("⚠️ Project manager initialization failed, continuing without project context", "WARNING")
                
        except Exception as e:
            self.bot.log(f"Failed to initialize project manager: {e}", "ERROR")
