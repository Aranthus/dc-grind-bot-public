import time
import logging

class ActivityManager:
    def __init__(self, bot_config=None):
        settings = bot_config.get('settings', {}) if bot_config else {}
        
        # Convert minutes to seconds
        self.active_duration = settings.get('active_duration', 3) * 60  # Default 3 minutes
        self.afk_duration = settings.get('afk_duration', 15) * 60      # Default 15 minutes
        self.max_messages = settings.get('message_limit', 15)          # Default 15 messages
        
        self.current_state = "active"  # "active" or "afk"
        self.state_start_time = time.time()
        self.message_count = 0
        
        # Logger setup - avoid duplicate handlers
        self.logger = logging.getLogger("ActivityManager")
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            
            # Create console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Create formatter
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            console_handler.setFormatter(formatter)
            
            # Add handler to logger
            self.logger.addHandler(console_handler)
        
    def can_send_message(self):
        current_time = time.time()
        
        # Durum kontrolü
        if self.current_state == "afk":
            remaining_afk = self.afk_duration - (current_time - self.state_start_time)
            print(f"🔴 AFK MODE - {remaining_afk/60:.1f} dk kaldı")
            
            # AFK süresini kontrol et
            if current_time - self.state_start_time >= self.afk_duration:
                # AFK süresi dolmuş, aktif moda geç
                self.current_state = "active"
                self.state_start_time = current_time
                self.message_count = 0
                print(f"🟢 ACTIVE MODE - {self.active_duration/60:.1f} dk süre, {self.max_messages} mesaj limiti")
                self.logger.info("Switching to active mode after AFK duration")
                return True
            return False
            
        # Aktif durumdaysa
        elif self.current_state == "active":
            remaining_time = self.active_duration - (current_time - self.state_start_time)
            remaining_messages = self.max_messages - self.message_count
            print(f"🟢 ACTIVE MODE - {remaining_time/60:.1f} dk kaldı, {remaining_messages} mesaj kaldı")
            
            # Mesaj limitini kontrol et
            if self.message_count >= self.max_messages:
                self.switch_to_afk()
                print(f"🔴 MESAJ LİMİTİ DOLDU ({self.message_count}/{self.max_messages}) - AFK MODE")
                self.logger.info(f"Message limit reached ({self.message_count}/{self.max_messages}), switching to AFK")
                return False
                
            # Aktif süreyi kontrol et
            if current_time - self.state_start_time >= self.active_duration:
                self.switch_to_afk()
                print(f"🔴 AKTİF SÜRE BİTTİ ({int(current_time - self.state_start_time)}s) - AFK MODE")
                self.logger.info(f"Active duration ended ({int(current_time - self.state_start_time)}s), switching to AFK")
                return False
                
            return True
    
    def switch_to_afk(self):
        self.current_state = "afk"
        self.state_start_time = time.time()
        self.message_count = 0
        
    def message_sent(self):
        self.message_count += 1
        remaining_messages = self.max_messages - self.message_count
        print(f"📤 MESAJ GÖNDERİLDİ - {self.message_count}/{self.max_messages} (kalan: {remaining_messages})")
        
    def is_afk(self):
        """Check if bot is currently in AFK state"""
        return self.current_state == "afk"
        

        
    def get_remaining_time(self):
        current_time = time.time()
        if self.current_state == "active":
            return max(0, self.active_duration - (current_time - self.state_start_time))
        else:
            return max(0, self.afk_duration - (current_time - self.state_start_time))
            
    def get_status(self):
        """Mevcut durumu ve kalan süreyi döndürür"""
        remaining = self.get_remaining_time()
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        time_str = f"{minutes:02d}:{seconds:02d}"
        
        return {
            'state': self.current_state,
            'remaining_time': remaining,
            'time_str': time_str,
            'message_count': self.message_count,
            'max_messages': self.max_messages
        }
