"""
Configuration module for the Legion Discord Bot
Handles environment variables and bot configuration.
"""

import os
import logging
from dotenv import load_dotenv
from constants import COMMAND_PREFIX

# Load environment variables
load_dotenv()

class Config:
    """Bot configuration class"""
    
    # Discord Bot Token
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    # Bot settings
    COMMAND_PREFIX = os.getenv('DISCORD_COMMAND_PREFIX', '!')

    # Admin users (Discord User IDs)
    ADMIN_USERS = [
        402169053013213195,  # Add your admin user ID here
        # Add more admin user IDs as needed
    ]
    
    # Logging configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'bot.log')
    
    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present"""
        if not cls.DISCORD_BOT_TOKEN:
            raise ValueError("DISCORD_BOT_TOKEN not found in environment variables!")
        return True
    
    @classmethod
    def is_admin(cls, user_id):
        """Check if a user ID is in the admin list"""
        return int(user_id) in cls.ADMIN_USERS
    
    @classmethod
    def setup_logging(cls):
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, cls.LOG_LEVEL.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(cls.LOG_FILE),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger('legion_bot')