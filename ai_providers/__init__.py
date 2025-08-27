from .base import AIProvider
from .gemini_provider import GeminiProvider
from .chatgpt_provider import ChatGPTProvider
from .claude_provider import ClaudeProvider
from .grok_provider import GrokProvider
# from .deepseek import DeepSeekProvider

def get_ai_provider(provider_type, api_key, settings=None):
    """AI provider factory"""
    providers = {
        'gemini': GeminiProvider,
        'chatgpt': ChatGPTProvider,
        'claude': ClaudeProvider,
        'grok': GrokProvider,
        # 'deepseek': DeepSeekProvider
    }
    
    provider_class = providers.get(provider_type)
    if not provider_class:
        raise ValueError(f"Unknown AI provider: {provider_type}")
        
    return provider_class(api_key, settings)
