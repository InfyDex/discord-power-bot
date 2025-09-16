"""
Legion Discord Bot
A multilingual Discord bot with greeting functionality and modular design.
"""

import discord
from discord.ext import commands
import asyncio
import os
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
        
        self.logger.info("Bot setup completed successfully!")
    
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