import google.generativeai as genai
import logging
import json
from datetime import datetime
from pathlib import Path
from .base import AIProvider

class GeminiProvider(AIProvider):
    def __init__(self, api_key, settings=None):
        super().__init__(api_key, settings)
        self.model = None
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
            "ai_response": ai_response,
            "provider": "gemini"
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
        
    async def initialize(self):
        """Initialize Gemini AI"""
        genai.configure(api_key=self.api_key)
        
        generation_config = {
            "temperature": self.settings.get('temperature', 0.9),
            "top_p": self.settings.get('top_p', 1),
            "top_k": self.settings.get('top_k', 40),
            "candidate_count": self.settings.get('candidate_count', 1),
            "max_output_tokens": self.settings.get('max_tokens', 2048),
        }
        
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]
        
        self.model = genai.GenerativeModel(
            model_name="gemini-pro",
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
    async def generate_response(self, system_prompt, message, user_id=None):
        """Generate response using Gemini"""
        if not self.model:
            await self.initialize()

        try:
            # Get or create chat for user
            chat = self.get_chat_history(user_id)
            if not chat:
                # Create new chat with system prompt only for new chats
                chat = self.model.start_chat(history=[])
                if system_prompt:
                    await chat.send_message_async(system_prompt)
                self.chat_histories[user_id] = chat

            # Send user message and get response
            response = await chat.send_message_async(message)
            response_text = response.text

            # Log the communication with system prompt only for new chats
            log_system_prompt = system_prompt if len(chat.history) <= 2 else ""
            self.log_ai_communication(log_system_prompt, message, response_text, user_id)

            return response_text

        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            self.logger.error(error_msg)
            return error_msg
        
    async def start_chat(self, system_prompt, user_id):
        """Start a new chat session"""
        if not self.model:
            await self.initialize()
            
        chat = self.model.start_chat(history=[])
        await chat.send_message_async(system_prompt)
        self.chat_histories[user_id] = chat
        return chat
        
    def get_chat_history(self, user_id):
        return self.chat_histories.get(user_id)
        
    async def cleanup(self):
        """Cleanup Gemini resources"""
        self.model = None
        self.chat_histories = {}
