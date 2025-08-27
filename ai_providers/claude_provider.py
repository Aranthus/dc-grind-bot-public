from anthropic import AsyncAnthropic
from .base import AIProvider

class ClaudeProvider(AIProvider):
    def __init__(self, api_key, settings=None):
        super().__init__(api_key, settings)
        self.client = None
        self.chat_histories = {}
        
    async def initialize(self):
        """Initialize Claude client"""
        self.client = AsyncAnthropic(api_key=self.api_key)
        
    async def generate_response(self, system_prompt, message, user_id=None):
        """Generate response using Claude"""
        if not self.client:
            await self.initialize()
            
        # Get or create chat history for user
        chat_history = self.get_chat_history(user_id)
        if not chat_history:
            chat_history = []
            self.chat_histories[user_id] = chat_history
            
        # Add user message to history
        chat_history.append({"role": "user", "content": message})
        
        try:
            # Convert chat history to Claude format
            claude_messages = []
            for msg in chat_history[-10:]:  # Keep last 10 messages
                if msg["role"] != "system":  # Skip system messages as Claude handles them separately
                    claude_messages.append(msg)
            
            response = await self.client.messages.create(
                model=self.settings.get('model', 'claude-3-opus-20240229'),
                max_tokens=self.settings.get('max_tokens', 2048),
                temperature=self.settings.get('temperature', 0.9),
                system=system_prompt,
                messages=claude_messages
            )
            
            # Add assistant's response to history
            assistant_message = response.content[0].text
            chat_history.append({"role": "assistant", "content": assistant_message})
            
            # Keep only last N messages to prevent context length issues
            max_history = 10  # Adjust this value as needed
            if len(chat_history) > max_history:
                chat_history = chat_history[-max_history:]
            
            return self.normalize_response(assistant_message)
            
        except Exception as e:
            print(f"Error generating Claude response: {str(e)}")
            return None

    async def start_chat(self, system_prompt, user_id):
        """Start a new chat session"""
        if not self.client:
            await self.initialize()
        
        # Initialize empty chat history
        chat_history = []
        self.chat_histories[user_id] = chat_history
        return chat_history

    def get_chat_history(self, user_id):
        return self.chat_histories.get(user_id)

    async def cleanup(self):
        """Cleanup Claude resources"""
        if self.client:
            await self.client.close()
