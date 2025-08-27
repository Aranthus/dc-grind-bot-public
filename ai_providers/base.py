from abc import ABC, abstractmethod
import logging

class AIProvider(ABC):
    def __init__(self, api_key: str, settings: dict = None):
        """Initialize the base AI provider."""
        self.api_key = api_key
        self.settings = settings or {}
        
        # Log API key status (first and last 4 chars for verification)
        if api_key:
            masked_key = f"{api_key[:4]}...{api_key[-4:]}"
            logging.info(f"Initializing {self.__class__.__name__} with API key: {masked_key}")
        else:
            logging.warning(f"No API key provided for {self.__class__.__name__}")
            
        self.chat_histories = {}
        self.supports_temperature = False  # Default to False
        
    @abstractmethod
    async def initialize(self):
        """Initialize the AI provider"""
        pass
        
    @abstractmethod
    async def generate_response(self, system_prompt, message, user_id=None):
        """Generate a response from the AI"""
        pass
    
    @abstractmethod
    async def start_chat(self, system_prompt, user_id):
        """Start a new chat session"""
        pass
        
    @abstractmethod
    async def cleanup(self):
        """Cleanup resources"""
        pass
        
    def normalize_response(self, response):
        """Normalize AI response to standard format"""
        return str(response).strip()
        
    def get_chat_history(self, user_id):
        """Get chat history for user"""
        return self.chat_histories.get(user_id, None)
