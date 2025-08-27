import openai
import logging
import json
from datetime import datetime
from pathlib import Path
from .base import AIProvider

class ChatGPTProvider(AIProvider):
    def __init__(self, api_key, settings=None):
        super().__init__(api_key, settings)
        self.client = None
        self.chat_histories = {}
        self.setup_logging()
        
    def setup_logging(self):
        """Setup AI communication logging"""
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Create a specific log file for AI communication
        log_file = log_dir / "ai_communication.log"
        
        # Configure logging
        self.logger = logging.getLogger("ai_communication")
        self.logger.setLevel(logging.INFO)
        
        # Create file handler
        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(handler)
        
    def log_ai_communication(self, system_prompt, user_message, ai_response, user_id=None):
        """Log AI communication details"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "system_prompt": system_prompt,
            "user_message": user_message,
            "ai_response": ai_response
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
        
    async def initialize(self):
        """Initialize OpenAI client"""
        self.client = openai.AsyncOpenAI(api_key=self.api_key)
        
    def get_chat_history(self, user_id):
        """Get chat history for user"""
        return self.chat_histories.get(user_id)
        
    async def generate_response(self, system_prompt, message, user_id=None):
        """Generate response using ChatGPT"""
        if not self.client:
            await self.initialize()
        
        # Get or create chat history for user
        chat_history = self.get_chat_history(user_id)
        if not chat_history:
            chat_history = []
            self.chat_histories[user_id] = chat_history
            # Add system prompt as first message only when creating new chat
            if system_prompt:
                chat_history.append({"role": "system", "content": system_prompt})
    
        # Add user message to history
        chat_history.append({"role": "user", "content": message})
        
        try:
            completion = await self.client.chat.completions.create(
                model=self.settings.get("model", "gpt-3.5-turbo"),
                messages=chat_history,
                temperature=self.settings.get("temperature", 0.9),
                max_tokens=self.settings.get("max_tokens", 2048),
                top_p=self.settings.get("top_p", 1)
            )
            
            # Add assistant's response to history
            assistant_message = completion.choices[0].message.content
            chat_history.append({"role": "assistant", "content": assistant_message})
            
            # Log the communication with system prompt only for new chats
            log_system_prompt = system_prompt if len(chat_history) <= 3 else ""
            self.log_ai_communication(log_system_prompt, message, assistant_message, user_id)
            
            # Keep only last N messages to prevent context length issues
            max_history = 10  # Adjust this value as needed
            if len(chat_history) > max_history:
                # Always keep system prompt if it exists
                if chat_history[0]["role"] == "system":
                    system_msg = chat_history[0]
                    chat_history = [system_msg] + chat_history[-(max_history-1):]
                else:
                    chat_history = chat_history[-max_history:]
            
            return assistant_message
            
        except Exception as e:
            self.logger.error(f"Error generating response: {str(e)}")
            return f"Error generating response: {str(e)}"
        
    async def start_chat(self, system_prompt, user_id):
        """Start a new chat session"""
        if not self.client:
            await self.initialize()
        
        # Initialize chat history with system prompt
        chat_history = [{"role": "system", "content": system_prompt}]
        self.chat_histories[user_id] = chat_history
        return chat_history

    async def cleanup(self):
        """Cleanup resources"""
        self.chat_histories = {}
        self.client = None
