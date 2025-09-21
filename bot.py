"""
Legion Discord Bot
A multilingual Discord bot with greeting functionality and modular design.
"""

import discord
from discord.ext import commands
import asyncio
import os
import shutil
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import Config


class LegionBot(commands.Bot):
    """Main bot class with enhanced functionality"""
    
    def __init__(self):
        # Setup bot configuration
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix=Config.COMMAND_PREFIX,
            intents=intents,
            help_command=commands.DefaultHelpCommand(
                no_category='General Commands'
            )
        )
        
        # Setup logging
        self.logger = Config.setup_logging()
        
        # Initialize scheduler
        self.scheduler = AsyncIOScheduler()
    
    def backup_pokemon_data(self):
        """Backup pokemon_data.json to D drive every 10 minutes"""
        try:
            source_file = os.path.join(os.path.dirname(__file__), 'pokemon_data.json')
            
            # Check if source file exists and has content
            if not os.path.exists(source_file):
                self.logger.warning(f"Source file {source_file} not found for backup")
                return
            
            # Check file size to ensure it's not empty
            file_size = os.path.getsize(source_file)
            if file_size < 100:  # Less than 100 bytes is likely not real pokemon data
                self.logger.warning(f"Source file {source_file} is too small ({file_size} bytes) - skipping backup")
                return
            
            # Create backup directory on D drive if it doesn't exist
            backup_dir = 'legion_bot_backups'
            os.makedirs(backup_dir, exist_ok=True)
            
            # Create timestamped backup filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'pokemon_data_backup_{timestamp}.json'
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Also maintain a latest backup without timestamp
            latest_backup_path = os.path.join(backup_dir, 'pokemon_data_latest.json')
            
            # Copy the file (this creates a copy, doesn't move or modify the original)
            shutil.copy2(source_file, backup_path)
            shutil.copy2(source_file, latest_backup_path)
            
            # Verify the backup was successful
            backup_size = os.path.getsize(backup_path)
            if backup_size == file_size:
                self.logger.info(f"Pokemon data backed up successfully to {backup_path} ({backup_size} bytes)")
                
                # Keep only the last 10 timestamped backups to save space
                self.cleanup_old_backups(backup_dir)
            else:
                self.logger.error(f"Backup verification failed - size mismatch: original {file_size}, backup {backup_size}")
                
        except Exception as e:
            self.logger.error(f"Failed to backup pokemon data: {e}")
    
    def cleanup_old_backups(self, backup_dir):
        """Keep only the last 10 timestamped backup files"""
        try:
            # Get all timestamped backup files
            backup_files = []
            for filename in os.listdir(backup_dir):
                if filename.startswith('pokemon_data_backup_') and filename.endswith('.json'):
                    filepath = os.path.join(backup_dir, filename)
                    backup_files.append((filepath, os.path.getctime(filepath)))
            
            # Sort by creation time (newest first)
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            # Remove files beyond the 10 most recent
            for filepath, _ in backup_files[10:]:
                os.remove(filepath)
                self.logger.info(f"Removed old backup: {os.path.basename(filepath)}")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old backups: {e}")
    
    async def setup_hook(self):
        """Setup hook called when bot is starting up"""
        # Load all cogs
        await self.load_cogs()
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            self.logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            self.logger.error(f"Failed to sync commands: {e}")
        
        # Start the backup scheduler
        self.start_backup_scheduler()
        
        self.logger.info("Bot setup completed successfully!")
    
    def start_backup_scheduler(self):
        """Start the backup scheduler with 10-minute intervals"""
        try:
            # Schedule backup every 10 minutes
            self.scheduler.add_job(
                self.backup_pokemon_data,
                'interval',
                minutes=10,
                id='pokemon_backup',
                replace_existing=True
            )
            
            # Start the scheduler
            self.scheduler.start()
            self.logger.info("Backup scheduler started - Pokemon data will be backed up every 10 minutes")
            
            # Perform initial backup
            self.backup_pokemon_data()
            
        except Exception as e:
            self.logger.error(f"Failed to start backup scheduler: {e}")
    
    async def load_cogs(self):
        """Load all cogs from the cogs directory"""
        cog_files = []
        
        # Get all Python files in cogs directory
        cogs_path = os.path.join(os.path.dirname(__file__), 'cogs')
        if os.path.exists(cogs_path):
            for filename in os.listdir(cogs_path):
                if filename.endswith('.py') and not filename.startswith('__'):
                    cog_files.append(f'cogs.{filename[:-3]}')
        
        # Load each cog
        for cog in cog_files:
            try:
                await self.load_extension(cog)
                self.logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                self.logger.error(f"Failed to load cog {cog}: {e}")
    
    async def on_ready(self):
        """Event triggered when bot is ready"""
        self.logger.info(f'{self.user} has connected to Discord!')
        self.logger.info(f'Bot is ready and listening for messages!')
        
        # Set bot status
        await self.change_presence(
            activity=discord.Game(name="Greeting people worldwide! 🌍")
        )
    
    async def close(self):
        """Cleanup when bot is shutting down"""
        if hasattr(self, 'scheduler') and self.scheduler.running:
            self.scheduler.shutdown()
            self.logger.info("Backup scheduler stopped")
        await super().close()


# Create bot instance
bot = LegionBot()

async def main():
    """Main function to run the bot with proper error handling"""
    try:
        # Validate configuration
        Config.validate_config()
        
        # Start the bot
        async with bot:
            await bot.start(Config.DISCORD_BOT_TOKEN)
            
    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("Please create a .env file with your bot token.")
        return 1
    except discord.LoginFailure:
        print("Error: Invalid bot token!")
        return 1
    except Exception as e:
        print(f"Error starting bot: {e}")
        return 1


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")