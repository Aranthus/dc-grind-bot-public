"""
Core package for Discord self-bot processing logic.

This package contains the core processing modules for message handling,
AI responses, and other bot logic.
"""

from .message_processor import MessageProcessor
from .bot_initializer import BotInitializer
from .conversation_manager import ConversationManager

__all__ = [
    'MessageProcessor',
    'BotInitializer',
    'ConversationManager'
]
