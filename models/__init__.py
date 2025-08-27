"""
Models package for Discord self-bot configuration.

This package contains all configuration-related classes and utilities.
"""

from .bot_config import (
    # Exceptions
    BotConfigurationError,
    AIProviderError,
    ChannelNotFoundError,
    
    # Configuration Classes
    AISettings,
    MessageSettings,
    ChatSettings,
    ReplyChances,
    ActivitySettings,
    BotSettings,
    BotConfig,
    
    # Utility Functions
    load_config,
    validate_bot_config
)

__all__ = [
    # Exceptions
    'BotConfigurationError',
    'AIProviderError', 
    'ChannelNotFoundError',
    
    # Configuration Classes
    'AISettings',
    'MessageSettings',
    'ChatSettings',
    'ReplyChances',
    'ActivitySettings',
    'BotSettings',
    'BotConfig',
    
    # Utility Functions
    'load_config',
    'validate_bot_config'
]
