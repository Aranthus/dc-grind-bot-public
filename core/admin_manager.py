"""
Admin Detection and Silence Manager
Handles admin detection and automatic bot silence mode when admins are active
"""

import time
import asyncio
from typing import Dict, Set, Optional, Any

class AdminManager:
    def __init__(self, bot):
        self.bot = bot
        self.admin_silence_end_time: float = 0
        self.detected_admins: Set[str] = set()
        self.admin_config: Dict[str, Any] = {}
        self.last_admin_activity: float = 0
        
    def update_admin_config(self, config: Dict[str, Any]):
        """Update admin configuration"""
        self.admin_config = config
        self.bot.log(f"👮‍♂️ Admin config updated: {config}", "INFO")
    
    def is_admin_silence_active(self) -> bool:
        """Check if bot is in admin silence mode"""
        if not self.admin_config.get('enabled', False):
            return False
            
        current_time = time.time()
        is_silenced = current_time < self.admin_silence_end_time
        
        if is_silenced:
            remaining_minutes = (self.admin_silence_end_time - current_time) / 60
            if remaining_minutes > 0:
                return True
                
        return False
    
    def get_admin_silence_info(self) -> Dict[str, Any]:
        """Get admin silence status information"""
        current_time = time.time()
        remaining_time = max(0, self.admin_silence_end_time - current_time)
        
        return {
            'is_active': self.is_admin_silence_active(),
            'remaining_minutes': remaining_time / 60,
            'detected_admins': list(self.detected_admins),
            'last_admin_activity_ago_minutes': (current_time - self.last_admin_activity) / 60 if self.last_admin_activity > 0 else None
        }
    
    def is_user_admin(self, message) -> bool:
        """Check if message author is an admin"""
        try:
            if not self.admin_config.get('enabled', False):
                return False
                
            user = message.author
            
            # Skip if user is the bot itself
            if user == self.bot.user:
                return False
            
            # 🎯 Check exception list (users who should NOT trigger admin silence)
            exception_user_ids = self.admin_config.get('exception_user_ids', [])
            if str(user.id) in exception_user_ids:
                self.bot.log(f"⚡ ADMIN EXCEPTION: {user.name} ({user.id}) is in exception list - no silence triggered", "WARNING")
                return False
            
            # 1. Check Discord administrator permissions
            if self.admin_config.get('detect_permissions', True):
                if hasattr(message, 'guild') and message.guild:
                    member = message.guild.get_member(user.id)
                    if member and member.guild_permissions.administrator:
                        self.bot.log(f"👮‍♂️ ADMIN DETECTED (permissions): {user.name} ({user.id})", "WARNING")
                        return True
            
            # 2. Check global admin IDs
            global_admin_ids = self.admin_config.get('global_admin_ids', [])
            if str(user.id) in global_admin_ids:
                self.bot.log(f"👮‍♂️ ADMIN DETECTED (global list): {user.name} ({user.id})", "WARNING")
                return True
            
            # 3. Check server-specific admin IDs
            if hasattr(message, 'guild') and message.guild:
                server_id = str(message.guild.id)
                server_admins = self.admin_config.get('server_specific_admins', {}).get(server_id, [])
                if str(user.id) in server_admins:
                    self.bot.log(f"👮‍♂️ ADMIN DETECTED (server {server_id} list): {user.name} ({user.id})", "WARNING")
                    return True
            
            # 4. Optional role detection (disabled by default)
            if self.admin_config.get('use_role_detection', False):
                admin_roles = self.admin_config.get('admin_roles', [])
                if admin_roles and hasattr(message, 'guild') and message.guild:
                    member = message.guild.get_member(user.id)
                    if member:
                        user_roles = [role.name for role in member.roles]
                        for admin_role in admin_roles:
                            if admin_role in user_roles:
                                self.bot.log(f"👮‍♂️ ADMIN DETECTED (role {admin_role}): {user.name} ({user.id})", "WARNING")
                                return True
                
            return False
            
        except Exception as e:
            self.bot.log(f"Error checking admin status: {e}", "ERROR")
            return False
    
    def trigger_admin_silence(self, admin_user):
        """Trigger admin silence mode when admin posts"""
        if not self.admin_config.get('enabled', False):
            return
            
        current_time = time.time()
        silence_duration = self.admin_config.get('silence_duration_hours', 3) * 3600
        
        # Extend silence period
        self.admin_silence_end_time = current_time + silence_duration
        self.last_admin_activity = current_time
        self.detected_admins.add(f"{admin_user.name}#{admin_user.discriminator}")
        
        # Log the silence activation
        end_time_readable = time.strftime('%H:%M', time.localtime(self.admin_silence_end_time))
        self.bot.log(f"🔇 ADMIN SILENCE ACTIVATED by {admin_user.name}!", "WARNING")
        self.bot.log(f"🕒 Bot will be silent until {end_time_readable} ({silence_duration/3600:.1f}h)", "WARNING")
        
        # Update activity manager if available (optional)
        if hasattr(self.bot, 'activity_manager'):
            try:
                # Try to force AFK state if method exists
                if hasattr(self.bot.activity_manager, 'force_activity_state'):
                    self.bot.activity_manager.force_activity_state('afk', duration=silence_duration)
                elif hasattr(self.bot.activity_manager, 'set_state'):
                    self.bot.activity_manager.set_state('afk')
            except Exception as e:
                self.bot.log(f"Note: Could not update activity state: {e}", "WARNING")
    
    def check_admin_message(self, message) -> bool:
        """
        Check if message is from admin and trigger silence if needed
        Returns True if admin detected, False otherwise
        """
        try:
            if self.is_user_admin(message):
                self.trigger_admin_silence(message.author)
                return True
            return False
            
        except Exception as e:
            self.bot.log(f"Error in admin message check: {e}", "ERROR")
            return False
    
    def should_bot_stay_silent(self) -> bool:
        """
        Main function to check if bot should stay silent due to admin activity
        Used by message processor and conversation manager
        """
        is_silenced = self.is_admin_silence_active()
        
        if is_silenced:
            silence_info = self.get_admin_silence_info()
            self.bot.log(f"🔇 Bot staying silent (admin mode): {silence_info['remaining_minutes']:.1f}min remaining", "WARNING")
            
        return is_silenced
    
    def force_end_admin_silence(self):
        """Manually end admin silence mode (for testing/debugging)"""
        if self.is_admin_silence_active():
            remaining_minutes = (self.admin_silence_end_time - time.time()) / 60
            self.bot.log(f"🔊 Admin silence mode ended manually ({remaining_minutes:.1f}min early)", "WARNING")
        else:
            self.bot.log("🔊 Admin silence was not active", "WARNING")
        
        self.admin_silence_end_time = 0
    
    def get_admin_stats(self) -> Dict[str, Any]:
        """Get admin detection statistics"""
        current_time = time.time()
        
        return {
            'enabled': self.admin_config.get('enabled', False),
            'silence_active': self.is_admin_silence_active(),
            'silence_remaining_minutes': max(0, (self.admin_silence_end_time - current_time) / 60),
            'silence_duration_hours': self.admin_config.get('silence_duration_hours', 3),
            'total_admins_detected': len(self.detected_admins),
            'detected_admins': list(self.detected_admins),
            'last_admin_activity_ago_minutes': (current_time - self.last_admin_activity) / 60 if self.last_admin_activity > 0 else None,
            'detection_methods': {
                'permissions': self.admin_config.get('detect_permissions', True),
                'role_detection': self.admin_config.get('use_role_detection', False),
                'global_admin_count': len(self.admin_config.get('global_admin_ids', [])),
                'server_specific_count': len(self.admin_config.get('server_specific_admins', {}))
            }
        }
