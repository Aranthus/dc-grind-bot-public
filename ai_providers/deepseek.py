from .base import AIProvider
import deepseek_ai as deepseek
import asyncio

class DeepSeekProvider(AIProvider):
    def __init__(self, api_key, settings=None):
        self.api_key = api_key
        self.settings = settings or {}
        self.client = None
        self.supports_temperature = True
        self.max_tokens = 4096
        self.initialized = False
        
    async def initialize(self):
        """Initialize the DeepSeek client"""
        if not self.initialized:
            try:
                self.client = deepseek.Client(api_key=self.api_key)
                self.initialized = True
            except Exception as e:
                print(f"Error initializing DeepSeek client: {str(e)}")
                raise
                
    async def cleanup(self):
        """Cleanup resources"""
        if self.client:
            try:
                await self.client.close()
            except:
                pass
        self.initialized = False
        
    async def start_chat(self, system_prompt):
        """Start a new chat with system prompt"""
        if not self.initialized:
            await self.initialize()
        try:
            self.current_chat = await self.client.chat.create(
                messages=[{"role": "system", "content": system_prompt}]
            )
            return True
        except Exception as e:
            print(f"Error starting chat: {str(e)}")
            return False
            
    async def generate_response(self, prompt, temperature=0.7):
        """Generate response from DeepSeek"""
        if not self.initialized:
            await self.initialize()
            
        try:
            response = await self.client.chat.create(
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=self.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return None
