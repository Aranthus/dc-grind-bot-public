"""
Server Knowledge Manager
Handles channel direction, server-specific knowledge, and smart suggestions
"""

import re
import asyncio
import json
import os
from typing import Dict, Any, Optional, List, Tuple

class ServerKnowledgeManager:
    def __init__(self, bot):
        self.bot = bot
        self.knowledge_config: Dict[str, Any] = {}
        self.discovered_channels: Dict[str, Any] = {}
        
    def update_knowledge_config(self, config: Dict[str, Any]):
        """Update server knowledge configuration"""
        self.knowledge_config = config
        
        # Get current project name from bot config
        if hasattr(self.bot, 'original_config') and self.bot.original_config:
            self.current_project = self.bot.original_config.get('general', {}).get('project_name', 'default')
        else:
            self.current_project = 'default'
        
        # Load project-specific channels from file
        self._load_project_channels()
        
        current_channels = getattr(self, 'project_channels', {})
        self.bot.log(f"📚 Server knowledge config updated for project '{self.current_project}': {len(current_channels)} channels mapped", "INFO")
        
        # Auto-discover channels if enabled
        if config.get('auto_discovery', True):
            asyncio.create_task(self.discover_server_channels())
    
    def _load_project_channels(self):
        """Load project-specific channel configuration from file"""
        project_file = f"projects/{self.current_project}.json"
        
        if os.path.exists(project_file):
            try:
                with open(project_file, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
                    self.project_channels = project_data.get('channels', {})
                    self.project_responses = project_data.get('common_responses', {})
                    self.bot.log(f"📁 Loaded project config from {project_file}", "INFO")
            except Exception as e:
                self.bot.log(f"⚠️ Failed to load project config {project_file}: {e}", "WARNING")
                self.project_channels = {}
                self.project_responses = {}
        else:
            self.bot.log(f"⚠️ Project config file not found: {project_file}", "WARNING")
            self.project_channels = {}
            self.project_responses = {}
    
    def analyze_message_for_channel_suggestions(self, message_content: str) -> Optional[Dict[str, Any]]:
        """
        Analyze message content and suggest appropriate channel if needed
        Returns channel suggestion info or None
        """
        if not self.knowledge_config.get('enabled', False):
            return None
            
        message_lower = message_content.lower()
    
        # Get project-specific channels from loaded config
        channels = getattr(self, 'project_channels', {})
        
        # Find best matching channel based on keywords
        best_match = None
        max_score = 0
        
        for channel_name, channel_info in channels.items():
            keywords = channel_info.get('keywords', [])
            score = self._calculate_keyword_score(message_lower, keywords)
            
            if score > max_score and score > 0:
                # Check if this channel actually exists (for auto-discovered channels)
                if self._channel_exists(channel_info):
                    max_score = score
                    best_match = {
                        'channel_name': channel_name,
                        'channel_mention': channel_info.get('channel_mention', f'#{channel_name}'),
                        'description': channel_info.get('description', ''),
                        'score': score,
                        'matched_keywords': self._get_matched_keywords(message_lower, keywords)
                    }
                else:
                    self.bot.log(f"⚠️ Channel {channel_name} configured but not found, skipping suggestion", "WARNING")
        
        # Only suggest if we have a good match (at least 1 keyword)
        if best_match and best_match['score'] >= 1:
            return best_match
        
        # Fallback: if no specific match found but message is help-seeking, suggest general help
        if self.should_suggest_channel(message_content):
            return self._get_generic_help_suggestion(message_content)
            
        return None
    
    def _calculate_keyword_score(self, message: str, keywords: List[str]) -> int:
        """Calculate how well message matches keywords"""
        score = 0
        for keyword in keywords:
            # Check for exact word matches (not just substring)
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', message):
                score += 2  # Exact word match
            elif keyword.lower() in message:
                score += 1  # Substring match
        return score
    
    def _get_matched_keywords(self, message: str, keywords: List[str]) -> List[str]:
        """Get list of keywords that matched in the message"""
        matched = []
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', message):
                matched.append(keyword)
        return matched
    
    def _channel_exists(self, channel_info: Dict[str, Any]) -> bool:
        """Check if a channel actually exists in the server"""
        try:
            # If it's auto-discovered, we have channel_id
            if channel_info.get('channel_id'):
                channel_id = channel_info['channel_id']
                channel = self.bot.get_channel(channel_id)
                return channel is not None
            
            # For manual config, check by mention or name
            channel_mention = channel_info.get('channel_mention', '')
            if channel_mention.startswith('#'):
                channel_name = channel_mention[1:]  # Remove #
                # Search in all guilds
                for guild in self.bot.guilds:
                    for channel in guild.text_channels:
                        if channel.name == channel_name:
                            return True
            
            # Default to True for non-auto-discovered channels to avoid breaking existing configs
            if not channel_info.get('auto_discovered', False):
                return True
                
            return False
            
        except Exception as e:
            self.bot.log(f"Error checking channel existence: {e}", "WARNING")
            return True  # Default to True to avoid breaking suggestions
    
    def _get_generic_help_suggestion(self, message_content: str) -> Optional[Dict[str, Any]]:
        """Get generic help suggestion when no specific channel matches"""
        try:
            # Find any available help channel
            available_channels = []
            
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    # Look for general help channels
                    if any(word in channel.name.lower() for word in ['general', 'help', 'chat', 'main']):
                        available_channels.append({
                            'name': channel.name,
                            'mention': channel.mention,
                            'type': 'general_help'
                        })
            
            if available_channels:
                # Prefer 'general' channel if available
                general_channel = next((ch for ch in available_channels if 'general' in ch['name'].lower()), None)
                if general_channel:
                    return {
                        'channel_name': 'general',
                        'channel_mention': f"#{general_channel['name']}",
                        'description': 'general discussions and help',
                        'score': 1,
                        'matched_keywords': ['help'],
                        'is_generic': True
                    }
                
                # Otherwise use first available help channel
                first_channel = available_channels[0]
                return {
                    'channel_name': 'help',
                    'channel_mention': f"#{first_channel['name']}",
                    'description': 'general help and discussions',
                    'score': 1,
                    'matched_keywords': ['help'],
                    'is_generic': True
                }
            
            return None
            
        except Exception as e:
            self.bot.log(f"Error getting generic help suggestion: {e}", "WARNING")
            return None
    
    def generate_channel_suggestion_text(self, suggestion: Dict[str, Any], message_type: str = "general") -> str:
        """
        Generate a natural channel suggestion response
        """
        channel_mention = suggestion['channel_mention']
        responses = self.knowledge_config.get('common_responses', {})
        
        # Choose response template based on context
        if any(keyword in suggestion['matched_keywords'] for keyword in ['whitelist', 'how to', 'guide', 'tutorial', 'instructions', 'faq']):
            template = responses.get('faq_help', 'Check {channel} for that info!')
        elif any(keyword in suggestion['matched_keywords'] for keyword in ['help', 'problem', 'issue', 'bug', 'error', 'broken', 'support']):
            template = responses.get('support_redirect', 'Head over to {channel} for help!')
        elif any(keyword in suggestion['matched_keywords'] for keyword in ['create', 'content', 'creator', 'art', 'design']):
            template = responses.get('creator_redirect', '{channel} might be better for that!')
        elif any(keyword in suggestion['matched_keywords'] for keyword in ['news', 'update', 'announcement', 'release', 'launch']):
            template = responses.get('announcement_redirect', 'Check {channel} for updates!')
        else:
            template = responses.get('general_redirect', 'Check {channel} for more info!')
        
        return template.format(channel=channel_mention)
    
    def should_suggest_channel(self, message_content: str, context: Dict[str, Any] = None) -> bool:
        """
        Determine if we should suggest a channel for this message
        More strict criteria for Discord replies
        """
        # Basic checks
        if not self.knowledge_config.get('enabled', False):
            return False
        
        message_lower = message_content.lower()
        
        # Look for CLEAR help-seeking patterns (more strict for replies)
        clear_help_patterns = [
            'how do i', 'how to', 'where to', 'where can i', 'need help',
            'can someone help', 'help me', 'where to check', 'how can i',
            'what do i do', 'need info', 'need guide', 'looking for help'
        ]
        
        # Check for clear help patterns
        for pattern in clear_help_patterns:
            if pattern in message_lower:
                return True
        
        # Question + specific keywords (whitelist, support, etc.)
        if '?' in message_content:
            specific_keywords = [
                'whitelist', 'support', 'problem', 'issue', 'bug', 'error',
                'guide', 'tutorial', 'instructions', 'creator', 'art', 'design'
            ]
            if any(keyword in message_lower for keyword in specific_keywords):
                return True
        
        return False
    
    def get_all_channels_info(self) -> str:
        """Get formatted string of all available channels for AI context"""
        if not self.knowledge_config.get('enabled', False):
            return ""
        
        channels = self.knowledge_config.get('channels', {})
        if not channels:
            return ""
        
        info_lines = ["Available server channels:"]
        for channel_name, channel_info in channels.items():
            mention = channel_info.get('channel_mention', f'#{channel_name}')
            description = channel_info.get('description', '')
            keywords = ', '.join(channel_info.get('keywords', [])[:3])  # First 3 keywords
            info_lines.append(f"- {mention}: {description} (keywords: {keywords})")
        
        return '\n'.join(info_lines)
    
    def process_message_for_channel_direction(self, message_content: str, current_channel=None) -> Optional[str]:
        """
        Main processing function - analyze message and return channel suggestion if appropriate
        Returns suggestion text or None
        """
        try:
            # Check if we should suggest a channel
            if not self.should_suggest_channel(message_content):
                return None
            
            # Analyze message for channel suggestions
            suggestion = self.analyze_message_for_channel_suggestions(message_content)
            
            if suggestion:
                # Check if user is already in the suggested channel
                if current_channel and self._is_same_channel(suggestion, current_channel):
                    self.bot.log(f"🚫 User already in suggested channel {suggestion['channel_mention']}, skipping suggestion", "INFO")
                    return None
                
                # Generate natural response with channel direction
                suggestion_text = self.generate_channel_suggestion_text(suggestion)
                
                # Log the suggestion
                self.bot.log(f"📍 Channel suggestion: {suggestion['channel_mention']} "
                           f"(score: {suggestion['score']}, keywords: {suggestion['matched_keywords']})", "INFO")
                
                return suggestion_text
            
            return None
            
        except Exception as e:
            self.bot.log(f"Error in channel direction processing: {e}", "ERROR")
            return None
    
    def _is_same_channel(self, suggestion: Dict[str, Any], current_channel) -> bool:
        """Check if suggestion points to the same channel user is currently in"""
        try:
            # Get suggested channel info
            suggested_mention = suggestion.get('channel_mention', '')
            suggested_id = suggestion.get('channel_id')
            
            # If we have channel_id, compare directly
            if suggested_id and hasattr(current_channel, 'id'):
                return str(suggested_id) == str(current_channel.id)
            
            # Compare by channel mention
            if suggested_mention and hasattr(current_channel, 'mention'):
                return suggested_mention == current_channel.mention
            
            # Compare by channel name
            if suggested_mention and hasattr(current_channel, 'name'):
                # Remove # from mention if present
                suggested_name = suggested_mention.lstrip('#')
                return suggested_name.lower() == current_channel.name.lower()
            
            return False
            
        except Exception as e:
            self.bot.log(f"Error comparing channels: {e}", "WARNING")
            return False
    
    async def discover_server_channels(self):
        """Auto-discover channels in all guilds and map them based on name patterns"""
        try:
            await asyncio.sleep(5)  # Wait for bot to be ready
            
            self.bot.log("🔍 Starting auto-discovery of server channels...", "INFO")
            
            # Channel name patterns for auto-mapping
            channel_patterns = {
                'faq': ['faq', 'help', 'guide', 'info', 'questions'],
                'support': ['support', 'help', 'ticket', 'bug', 'issue'],
                'announcements': ['announcement', 'news', 'update', 'info'],
                'general': ['general', 'chat', 'main', 'lobby'],
                'whitelist': ['whitelist', 'wl', 'access'],
                'rules': ['rules', 'rule', 'guideline'],
                'welcome': ['welcome', 'intro', 'start']
            }
            
            discovered = {}
            total_channels = 0
            
            # Scan all guilds the bot is in
            for guild in self.bot.guilds:
                self.bot.log(f"🏠 Scanning guild: {guild.name} ({guild.id})", "INFO")
                
                for channel in guild.text_channels:
                    total_channels += 1
                    channel_name_lower = channel.name.lower()
                    
                    # Try to match channel name to our patterns
                    for category, patterns in channel_patterns.items():
                        for pattern in patterns:
                            if pattern in channel_name_lower:
                                if category not in discovered:
                                    discovered[category] = []
                                
                                discovered[category].append({
                                    'name': channel.name,
                                    'id': channel.id,
                                    'mention': channel.mention,
                                    'guild': guild.name,
                                    'guild_id': guild.id
                                })
                                
                                self.bot.log(f"📍 Found {category} channel: {channel.mention} in {guild.name}", "INFO")
                                break
            
            self.discovered_channels = discovered
            
            # Update knowledge config with discovered channels
            self._update_config_with_discoveries(discovered)
            
            self.bot.log(f"✅ Auto-discovery complete: {len(discovered)} categories found across {total_channels} channels", "INFO")
            
        except Exception as e:
            self.bot.log(f"Error in channel auto-discovery: {e}", "ERROR")
    
    def _update_config_with_discoveries(self, discovered: Dict[str, List[Dict]]):
        """Update knowledge config with auto-discovered channels"""
        try:
            # Merge discovered channels with existing config
            existing_channels = self.knowledge_config.get('channels', {})
            
            for category, channels in discovered.items():
                if channels:  # Only add if we found channels
                    # Use the first found channel for the mention
                    primary_channel = channels[0]
                    
                    # Create or update channel config
                    if category not in existing_channels:
                        # Define default keywords for each category
                        default_keywords = {
                            'faq': ['whitelist', 'how to', 'help', 'question', 'guide', 'tutorial', 'info'],
                            'support': ['problem', 'issue', 'bug', 'error', 'not working', 'broken', 'help'],
                            'announcements': ['news', 'update', 'announcement', 'release', 'launch'],
                            'general': ['chat', 'talk', 'discuss', 'conversation'],
                            'whitelist': ['whitelist', 'wl', 'access', 'mint', 'allowlist'],
                            'rules': ['rule', 'regulation', 'guideline', 'policy'],
                            'welcome': ['welcome', 'intro', 'start', 'new']
                        }
                        
                        descriptions = {
                            'faq': 'frequently asked questions and guides',
                            'support': 'technical support and issue resolution',
                            'announcements': 'project updates and news',
                            'general': 'general discussions and chat',
                            'whitelist': 'whitelist access and requirements',
                            'rules': 'server rules and guidelines',
                            'welcome': 'welcome information for new members'
                        }
                        
                        existing_channels[category] = {
                            'keywords': default_keywords.get(category, []),
                            'channel_mention': f"#{primary_channel['name']}",
                            'description': descriptions.get(category, f'{category} related discussions'),
                            'auto_discovered': True,
                            'channel_id': primary_channel['id'],
                            'guild_id': primary_channel['guild_id']
                        }
                    else:
                        # Update existing config with discovered channel mention
                        existing_channels[category]['channel_mention'] = f"#{primary_channel['name']}"
                        existing_channels[category]['channel_id'] = primary_channel['id']
                        existing_channels[category]['auto_discovered'] = True
            
            # Update the config
            self.knowledge_config['channels'] = existing_channels
            
            self.bot.log(f"🔄 Updated knowledge config with {len(existing_channels)} channels", "INFO")
            
        except Exception as e:
            self.bot.log(f"Error updating config with discoveries: {e}", "ERROR")
    
    def get_discovery_info(self) -> Dict[str, Any]:
        """Get information about auto-discovered channels"""
        return {
            'discovered_channels': self.discovered_channels,
            'discovery_enabled': self.knowledge_config.get('auto_discovery', True),
            'total_categories': len(self.discovered_channels),
            'total_discovered': sum(len(channels) for channels in self.discovered_channels.values())
        }
    
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get server knowledge statistics"""
        channels = self.knowledge_config.get('channels', {})
        
        total_keywords = sum(len(ch.get('keywords', [])) for ch in channels.values())
        auto_discovered = sum(1 for ch in channels.values() if ch.get('auto_discovered', False))
        
        return {
            'enabled': self.knowledge_config.get('enabled', False),
            'auto_discovery': self.knowledge_config.get('auto_discovery', True),
            'total_channels': len(channels),
            'auto_discovered_channels': auto_discovered,
            'manual_channels': len(channels) - auto_discovered,
            'total_keywords': total_keywords,
            'channels_configured': list(channels.keys()),
            'discovery_info': self.get_discovery_info()
        }
