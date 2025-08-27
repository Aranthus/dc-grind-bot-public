"""
Project Manager Module

Manages project-specific information and context for the Discord bot.
Each bot instance can be configured for a specific project and will automatically
load that project's information into the AI context.
"""

import asyncio
from typing import Dict, Any, Optional, List
from supabase import create_client, Client


class ProjectManager:
    def __init__(self, bot):
        self.bot = bot
        self.supabase: Optional[Client] = None
        self.current_project: Optional[Dict[str, Any]] = None
        self.project_context: str = ""
        
    async def initialize(self) -> bool:
        """Initialize project manager and load project info"""
        try:
            # Initialize Supabase client
            await self._init_supabase()
            
            # Load project info if project_name is configured
            project_name = self.bot.original_config.get('general', {}).get('project_name')
            if project_name:
                await self.load_project_info(project_name)
                self.bot.log(f"🏢 Loaded project context: {project_name}", "INFO")
            else:
                self.bot.log("⚠️ No project_name configured, running without project context", "WARNING")
            
            return True
            
        except Exception as e:
            self.bot.log(f"Error initializing project manager: {e}", "ERROR")
            return False
    
    async def _init_supabase(self):
        """Initialize Supabase client"""
        try:
            supabase_config = self.bot.original_config.get('supabase', {})
            supabase_url = supabase_config.get('url')
            supabase_key = supabase_config.get('anon_key')
            
            self.bot.log(f"DEBUG: Config keys: {list(self.bot.original_config.keys())}", "INFO")
            self.bot.log(f"DEBUG: Supabase config: {supabase_config}", "INFO")
            
            if not supabase_url or not supabase_key:
                raise Exception(f"Missing Supabase credentials - URL: {supabase_url}, Key: {'***' if supabase_key else None}")
            
            self.supabase = create_client(supabase_url, supabase_key)
            self.bot.log("🔗 Connected to Supabase for project info", "INFO")
            
        except Exception as e:
            self.bot.log(f"Failed to initialize Supabase: {e}", "ERROR")
            raise
    
    async def load_project_info(self, project_name: str) -> bool:
        """Load project information from database"""
        try:
            if not self.supabase:
                self.bot.log("Supabase not initialized", "ERROR")
                return False
            
            # Query project info
            response = await asyncio.to_thread(
                lambda: self.supabase.table('project_info').select('*').eq('project_name', project_name).execute()
            )
            
            if response.data and len(response.data) > 0:
                self.current_project = response.data[0]
                self._generate_project_context()
                self.bot.log(f"✅ Loaded project: {self.current_project['project_title']}", "INFO")
                return True
            else:
                self.bot.log(f"❌ Project '{project_name}' not found in database", "WARNING")
                return False
                
        except Exception as e:
            self.bot.log(f"Error loading project info: {e}", "ERROR")
            return False
    
    def _generate_project_context(self):
        """Generate formatted project context for AI"""
        if not self.current_project:
            self.project_context = ""
            return
        
        project = self.current_project
        
        context_parts = [
            f"=== PROJECT CONTEXT ===",
            f"Project: {project['project_title']}",
            f"Description: {project['description']}"
        ]
        
        if project.get('key_features'):
            features = ', '.join(project['key_features'])
            context_parts.append(f"Key Features: {features}")
        
        if project.get('community_info'):
            context_parts.append(f"Community: {project['community_info']}")
        
        if project.get('tokenomics'):
            context_parts.append(f"Tokenomics: {project['tokenomics']}")
        
        if project.get('roadmap_highlights'):
            context_parts.append(f"Roadmap: {project['roadmap_highlights']}")
        
        if project.get('team_info'):
            context_parts.append(f"Team: {project['team_info']}")
        
        context_parts.append("=== END PROJECT CONTEXT ===")
        
        self.project_context = "\n".join(context_parts)
    
    def get_project_context(self) -> str:
        """Get formatted project context for AI prompts"""
        return self.project_context
    
    def get_project_info(self) -> Optional[Dict[str, Any]]:
        """Get current project information"""
        return self.current_project
    
    def get_project_name(self) -> Optional[str]:
        """Get current project name"""
        return self.current_project.get('project_name') if self.current_project else None
    
    def get_project_title(self) -> Optional[str]:
        """Get current project title"""
        return self.current_project.get('project_title') if self.current_project else None
    
    async def add_project(self, project_data: Dict[str, Any]) -> bool:
        """Add new project to database"""
        try:
            if not self.supabase:
                self.bot.log("Supabase not initialized", "ERROR")
                return False
            
            response = await asyncio.to_thread(
                lambda: self.supabase.table('project_info').insert(project_data).execute()
            )
            
            if response.data:
                self.bot.log(f"✅ Added project: {project_data['project_title']}", "INFO")
                return True
            else:
                self.bot.log(f"❌ Failed to add project", "ERROR")
                return False
                
        except Exception as e:
            self.bot.log(f"Error adding project: {e}", "ERROR")
            return False
    
    async def update_project(self, project_name: str, updates: Dict[str, Any]) -> bool:
        """Update existing project"""
        try:
            if not self.supabase:
                self.bot.log("Supabase not initialized", "ERROR")
                return False
            
            updates['updated_at'] = 'NOW()'
            
            response = await asyncio.to_thread(
                lambda: self.supabase.table('project_info').update(updates).eq('project_name', project_name).execute()
            )
            
            if response.data:
                self.bot.log(f"✅ Updated project: {project_name}", "INFO")
                # Reload if this is current project
                if self.current_project and self.current_project['project_name'] == project_name:
                    await self.load_project_info(project_name)
                return True
            else:
                self.bot.log(f"❌ Failed to update project", "ERROR")
                return False
                
        except Exception as e:
            self.bot.log(f"Error updating project: {e}", "ERROR")
            return False
    
    async def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects"""
        try:
            if not self.supabase:
                self.bot.log("Supabase not initialized", "ERROR")
                return []
            
            response = await asyncio.to_thread(
                lambda: self.supabase.table('project_info').select('project_name, project_title, description').execute()
            )
            
            return response.data if response.data else []
            
        except Exception as e:
            self.bot.log(f"Error listing projects: {e}", "ERROR")
            return []
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.supabase:
                # Supabase client doesn't need explicit cleanup
                pass
            self.bot.log("🧹 Project manager cleaned up", "INFO")
        except Exception as e:
            self.bot.log(f"Error during project manager cleanup: {e}", "ERROR")
