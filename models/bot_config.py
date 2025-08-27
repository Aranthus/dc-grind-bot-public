"""
Bot Configuration Models

This module contains all configuration-related classes and validation functions
for the Discord self-bot.
"""

import json
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field

# Constants (imported from main module)
DEFAULT_BUFFER_TIMEOUT = 3.5
DEFAULT_TYPING_TIME = 2.0
DEFAULT_TEMPERATURE = 0.9
DEFAULT_CHUNK_SIZE = 2000

# Custom Exceptions
class BotConfigurationError(Exception):
    """Raised when bot configuration is invalid"""
    pass

class AIProviderError(Exception):
    """Raised when AI provider initialization fails"""
    pass

class ChannelNotFoundError(Exception):
    """Raised when specified channels are not found"""
    pass

# Configuration Classes
@dataclass
class AISettings:
    """AI provider settings"""
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = 2048
    top_p: float = 1.0
    top_k: int = 40
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = 0
    disable_chunking: bool = False
    model: str = "gpt-3.5-turbo"

@dataclass
class MessageSettings:
    """Message handling settings"""
    buffer_timeout: float = DEFAULT_BUFFER_TIMEOUT
    typing_indicator_time: float = DEFAULT_TYPING_TIME
    edit_wait_time: Dict[str, float] = field(default_factory=lambda: {'min': 1.0, 'max': 3.0})
    message_cooldown: float = 0.0

@dataclass
class ChatSettings:
    """Chat behavior settings"""
    chat_cooldown: int = 1800  # 30 minutes
    min_silence_duration: int = 1800  # 30 minutes
    max_silence_duration: int = 3600  # 1 hour

@dataclass
class ReplyChances:
    """Reply probability settings"""
    direct_mention: float = 1.0
    indirect_mention: float = 1.0
    group_mention: float = 1.0
    reply_to_bot: float = 1.0
    question: float = 1.0
    normal_chat: float = 1.0
    reply_chain: float = 1.0

@dataclass
class ActivitySettings:
    """Activity management settings"""
    online_hour_start: int = 11
    online_minute_start: int = 0
    online_hour_end: int = 0
    online_minute_end: int = 0
    active_duration: int = 10  # minutes
    afk_duration: int = 5  # minutes
    message_limit: int = 15

@dataclass
class BotSettings:
    """Main bot settings container"""
    ai_provider: str = 'gemini'
    prompt_type: str = 'tryprompt1'
    greetings: List[str] = field(default_factory=lambda: [
        "hello", "hi", "hey", "gm", "sup", "heya"
    ])
    ai_settings: AISettings = field(default_factory=AISettings)
    chat_settings: ChatSettings = field(default_factory=ChatSettings)
    reply_chances: ReplyChances = field(default_factory=ReplyChances)
    activity_settings: ActivitySettings = field(default_factory=ActivitySettings)

@dataclass
class BotConfig:
    """Complete bot configuration"""
    id: str
    name: str
    discord_token: str
    api_keys: Dict[str, str]
    channels: List[str]
    active: bool = False
    settings: BotSettings = field(default_factory=BotSettings)
    message_settings: MessageSettings = field(default_factory=MessageSettings)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BotConfig':
        """Create BotConfig from dictionary"""
        # Extract nested settings
        settings_data = data.get('settings', {})
        message_settings_data = data.get('message_settings', {})
        
        # Create nested objects
        ai_settings = AISettings(**settings_data.get('ai_settings', {}))
        chat_settings = ChatSettings(**settings_data.get('chat_settings', {}))
        reply_chances = ReplyChances(**settings_data.get('reply_chances', {}))
        activity_settings = ActivitySettings(**{
            k: v for k, v in settings_data.items() 
            if k in ['online_hour_start', 'online_minute_start', 'online_hour_end', 
                    'online_minute_end', 'active_duration', 'afk_duration', 'message_limit']
        })
        
        # Create main settings object
        bot_settings = BotSettings(
            ai_provider=settings_data.get('ai_provider', 'gemini'),
            prompt_type=settings_data.get('prompt_type', 'tryprompt1'),
            greetings=settings_data.get('greetings', ["hello", "hi", "hey", "gm", "sup", "heya"]),
            ai_settings=ai_settings,
            chat_settings=chat_settings,
            reply_chances=reply_chances,
            activity_settings=activity_settings
        )
        
        message_settings = MessageSettings(**message_settings_data)
        
        return cls(
            id=data['id'],
            name=data['name'],
            discord_token=data['discord_token'],
            api_keys=data['api_keys'],
            channels=data['channels'],
            active=data.get('active', False),
            settings=bot_settings,
            message_settings=message_settings
        )

# Utility Functions
def load_config() -> Optional[Dict[str, Any]]:
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            return config
    except Exception as e:
        print(f"Error loading config: {str(e)}")
        return None

def validate_bot_config(bot_config: Union[Dict[str, Any], BotConfig]) -> None:
    """Validate bot configuration and raise appropriate errors"""
    if isinstance(bot_config, dict):
        # Legacy validation for dict-based config
        required_fields = ['discord_token', 'id', 'name']
        
        for field in required_fields:
            if field not in bot_config:
                raise BotConfigurationError(f"Missing required field: {field}")
        
        if not bot_config['discord_token']:
            raise BotConfigurationError("Discord token cannot be empty")
        
        if not bot_config.get('channels'):
            raise BotConfigurationError("At least one channel must be specified")
        
        # Validate AI provider settings
        ai_provider = bot_config.get('settings', {}).get('ai_provider', 'gemini')
        api_keys = bot_config.get('api_keys', {})
        
        if ai_provider not in api_keys or not api_keys[ai_provider]:
            raise BotConfigurationError(f"API key for {ai_provider} is missing or empty")
    else:
        # Validation for BotConfig dataclass
        if not bot_config.discord_token:
            raise BotConfigurationError("Discord token cannot be empty")
        
        if not bot_config.channels:
            raise BotConfigurationError("At least one channel must be specified")
        
        # Validate AI provider settings
        ai_provider = bot_config.settings.ai_provider
        if ai_provider not in bot_config.api_keys or not bot_config.api_keys[ai_provider]:
            raise BotConfigurationError(f"API key for {ai_provider} is missing or empty")
