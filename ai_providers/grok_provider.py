import aiohttp
import json
from .base import AIProvider


class GrokProvider(AIProvider):
    """Grok AI Provider using xAI API"""
    
    def __init__(self, api_key: str, settings: dict = None):
        super().__init__(api_key, settings)
        self.client = None
        self.chat_histories = {}
        self.supports_temperature = True  # Grok supports temperature
        self.api_url = "https://api.x.ai/v1/chat/completions"
        
    async def initialize(self) -> None:
        """Initialize Grok client"""
        self.client = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        if self.client and not self.client.closed:
            await self.client.close()
        
    async def generate_response(self, system_prompt: str, message: str, user_id: str = None, temperature: float = None) -> str:
        """Generate response using Grok"""
        if not self.client:
            await self.initialize()
            
        # Get or create chat history for user
        chat_history = self.get_chat_history(user_id)
        if not chat_history:
            chat_history = [{"role": "system", "content": system_prompt}]
            self.chat_histories[user_id] = chat_history
            
        # Add user message to history
        chat_history.append({"role": "user", "content": message})
        
        try:
            # Prepare request payload
            payload = {
                "model": self.settings.get('model', 'grok-beta'),
                "messages": chat_history[-20:],  # Keep last 20 messages
                "max_tokens": self.settings.get('max_tokens', 2048),
                "temperature": temperature or self.settings.get('temperature', 0.9),
                "stream": False
            }
            
            # Make API request
            async with self.client.post(self.api_url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    assistant_message = data['choices'][0]['message']['content']
                    
                    # Add assistant's response to history
                    chat_history.append({"role": "assistant", "content": assistant_message})
                    
                    # Keep only last N messages to prevent context length issues
                    max_history = 20
                    if len(chat_history) > max_history:
                        # Keep system message and last messages
                        system_msg = chat_history[0] if chat_history[0]["role"] == "system" else None
                        recent_messages = chat_history[-max_history+1:] if system_msg else chat_history[-max_history:]
                        chat_history = ([system_msg] if system_msg else []) + recent_messages
                    
                    return self.normalize_response(assistant_message)
                else:
                    error_text = await response.text()
                    print(f"Grok API Error {response.status}: {error_text}")
                    return None
                    
        except Exception as e:
            print(f"Error generating Grok response: {str(e)}")
            return None
            
    async def start_chat(self, system_prompt: str, user_id: str) -> list:
        """Start a new chat session"""
        if not self.client:
            await self.initialize()
            
        # Initialize chat history with system prompt
        chat_history = [{"role": "system", "content": system_prompt}]
        self.chat_histories[user_id] = chat_history
        return chat_history
        
    def get_chat_history(self, user_id: str) -> list:
        """Get chat history for user"""
        return self.chat_histories.get(user_id)
        
    async def get_response(self, prompt: str, user_id: str = None, **kwargs) -> str:
        """Get response from Grok AI - compatibility method"""
        # Mevcut prompt sistemini kullan
        system_prompt = kwargs.get('system_prompt', prompt)
        temperature = kwargs.get('temperature', self.settings.get('temperature', 0.9))
        
        return await self.generate_response(
            system_prompt=system_prompt,
            message=kwargs.get('message', ''),
            user_id=user_id,
            temperature=temperature
        )

    async def cleanup(self) -> None:
        """Cleanup Grok resources"""
        if self.client:
            await self.client.close()
            self.client = None
