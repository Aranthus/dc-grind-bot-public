"""
Memory Management Module

Handles all conversation memory, user context, and database operations
for human-like bot behavior.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from supabase import create_client, Client
import json
import re


class MemoryManager:
    """Manages conversation memory and user context using Supabase"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
    async def save_conversation(
        self, 
        channel_id: str, 
        user_id: str, 
        username: str, 
        message_content: str,
        bot_response: str = None,
        bot_username: str = None,
        message_type: str = 'casual',
        topics: List[str] = None,
        sentiment: str = 'neutral'
    ) -> bool:
        """Save conversation to database"""
        try:
            data = {
                'channel_id': channel_id,
                'user_id': user_id,
                'username': username,
                'message_content': message_content,
                'bot_response': bot_response,
                'bot_username': bot_username,
                'message_type': message_type,
                'topics': topics or [],
                'sentiment': sentiment
            }
            
            result = self.supabase.table('conversation_history').insert(data).execute()
            
            # Update user memory
            await self.update_user_memory(user_id, username, topics, message_type)
            
            return True
            
        except Exception as e:
            print(f"Error saving conversation: {str(e)}")
            return False
    
    async def get_user_context(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get user context and recent conversation history"""
        try:
            # Get user memory
            user_memory = self.supabase.table('user_memory')\
                .select('*')\
                .eq('user_id', user_id)\
                .execute()
            
            # Get recent conversations
            recent_conversations = self.supabase.table('conversation_history')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('timestamp', desc=True)\
                .limit(limit)\
                .execute()
            
            return {
                'user_memory': user_memory.data[0] if user_memory.data else None,
                'recent_conversations': recent_conversations.data,
                'has_history': len(recent_conversations.data) > 0
            }
            
        except Exception as e:
            print(f"Error getting user context: {str(e)}")
            return {'user_memory': None, 'recent_conversations': [], 'has_history': False}
    
    async def update_user_memory(
        self, 
        user_id: str, 
        username: str, 
        topics: List[str] = None,
        message_type: str = 'casual'
    ) -> bool:
        """Update or create user memory"""
        try:
            # Check if user exists
            existing = self.supabase.table('user_memory')\
                .select('*')\
                .eq('user_id', user_id)\
                .execute()
            
            if existing.data:
                # Update existing user
                user = existing.data[0]
                updated_topics = list(set((user.get('preferred_topics') or []) + (topics or [])))
                
                update_data = {
                    'last_interaction': datetime.now().isoformat(),
                    'interaction_count': user.get('interaction_count', 0) + 1,
                    'preferred_topics': updated_topics[:10],  # Keep only top 10 topics
                    'relationship_strength': min(1.0, user.get('relationship_strength', 0.1) + 0.02)
                }
                
                self.supabase.table('user_memory')\
                    .update(update_data)\
                    .eq('user_id', user_id)\
                    .execute()
            else:
                # Create new user
                new_user = {
                    'user_id': user_id,
                    'username': username,
                    'preferred_topics': topics or [],
                    'conversation_style': self._detect_conversation_style(message_type),
                    'relationship_strength': 0.1,
                    'personality_notes': f'New user, prefers {message_type} conversations'
                }
                
                self.supabase.table('user_memory')\
                    .insert(new_user)\
                    .execute()
            
            return True
            
        except Exception as e:
            print(f"Error updating user memory: {str(e)}")
            return False
    
    async def analyze_conversation_flow(self, channel_id: str, recent_messages: List[Dict]) -> Dict[str, Any]:
        """Analyze current conversation flow and determine bot participation"""
        try:
            if len(recent_messages) < 2:
                return {'should_participate': True, 'conversation_type': 'general_chat'}
            
            # Extract participant IDs
            participants = [msg.get('author_id') for msg in recent_messages[-5:]]
            unique_participants = list(set(participants))
            
            # Determine conversation type
            if len(unique_participants) == 2 and len(recent_messages) >= 3:
                # Check if last 3 messages are from same 2 people
                last_3_authors = [msg.get('author_id') for msg in recent_messages[-3:]]
                if len(set(last_3_authors)) <= 2:
                    conversation_type = 'private_chat'
                    should_participate = False
                else:
                    conversation_type = 'group_discussion'
                    should_participate = True
            else:
                conversation_type = 'group_discussion'
                should_participate = True
            
            # Check timing
            if recent_messages:
                last_message_time = datetime.fromisoformat(recent_messages[-1].get('timestamp'))
                time_since_last = datetime.now() - last_message_time
                
                if time_since_last > timedelta(minutes=2):
                    should_participate = True  # Long silence, can join
            
            return {
                'should_participate': should_participate,
                'conversation_type': conversation_type,
                'active_participants': unique_participants,
                'participant_count': len(unique_participants)
            }
            
        except Exception as e:
            print(f"Error analyzing conversation flow: {str(e)}")
            return {'should_participate': True, 'conversation_type': 'general_chat'}
    
    async def get_contextual_prompt(self, user_id: str, current_message: str) -> str:
        """Generate contextual prompt based on user history"""
        try:
            context = await self.get_user_context(user_id)
            
            if not context['has_history']:
                return f"New user message: {current_message}"
            
            user_memory = context['user_memory']
            recent_convos = context['recent_conversations'][:3]  # Last 3 conversations
            
            # Build context prompt
            context_prompt = f"""
BACKGROUND INFO (NEVER MENTION THIS):
- User: {user_memory.get('username', 'someone')}
- Style: {user_memory.get('conversation_style', 'casual')}

CURRENT MESSAGE: {current_message}

🚨 CRITICAL RULES:
- This is a FRESH conversation - no history exists
- Respond ONLY to their current message
- NEVER reference any past topics, conversations, or context
- Act like you're meeting them for the first time in this conversation
- Be natural and casual but don't bring up anything from before
- If they don't mention something in current message, DON'T bring it up
- Be natural but treat each conversation as NEW

FORBIDDEN PHRASES:
- "Still curious about..."
- "Remember..."
- "Last time we talked..."
- "You mentioned..."
- Any reference to past conversations or topics"""
            
            return context_prompt
            
        except Exception as e:
            print(f"Error generating contextual prompt: {str(e)}")
            return f"Message: {current_message}"
    
    async def extract_topics(self, message: str) -> List[str]:
        """Extract topics from message content"""
        crypto_keywords = ['crypto', 'bitcoin', 'btc', 'ethereum', 'eth', 'trading', 'market', 'pump', 'dump', 'bullish', 'bearish']
        gaming_keywords = ['game', 'gaming', 'play', 'steam', 'xbox', 'ps5', 'nintendo']
        tech_keywords = ['tech', 'ai', 'programming', 'code', 'software', 'hardware', 'computer']
        
        topics = []
        message_lower = message.lower()
        
        if any(keyword in message_lower for keyword in crypto_keywords):
            topics.append('crypto')
        if any(keyword in message_lower for keyword in gaming_keywords):
            topics.append('gaming')
        if any(keyword in message_lower for keyword in tech_keywords):
            topics.append('tech')
        if '?' in message:
            topics.append('question')
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'sup']):
            topics.append('greeting')
        
        return topics or ['general']
    
    def _detect_conversation_style(self, message_type: str) -> str:
        """Detect conversation style from message type"""
        style_map = {
            'greeting': 'friendly',
            'question': 'technical',
            'casual': 'casual',
            'topic_change': 'casual'
        }
        return style_map.get(message_type, 'casual')
    
    def _get_relationship_description(self, strength: float) -> str:
        """Convert relationship strength to description"""
        if strength < 0.2:
            return "new/stranger"
        elif strength < 0.5:
            return "acquaintance"
        elif strength < 0.8:
            return "friend"
        else:
            return "close friend"
    
    def _format_time_ago(self, timestamp: str) -> str:
        """Format timestamp to human readable time ago"""
        try:
            past_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now()
            diff = now - past_time
            
            if diff.days > 0:
                return f"{diff.days} days ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hours ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} minutes ago"
            else:
                return "just now"
        except:
            return "recently"
