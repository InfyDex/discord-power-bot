# Legion Discord Bot

A multilingual Discord bot with a modular architecture designed for easy expansion and maintenance.

## Features

- **Multilingual Greetings**: Supports greetings in 30+ languages including English, Hindi, Spanish, French, German, Japanese, Arabic, and many more
- **Smart Mention Response**: Responds helpfully when mentioned
- **Modular Design**: Built with Discord.py cogs for easy feature addition
- **Error Handling**: Comprehensive error handling with user-friendly messages
- **Logging**: Built-in logging system for debugging and monitoring
- **Utility Commands**: Bot information, uptime, ping, and admin commands

## Project Structure

```
legion_discord_bot/
├── bot.py              # Main bot file
├── config.py           # Configuration and environment handling
├── constants.py        # Bot constants (greetings, messages, etc.)
├── requirements.txt    # Python dependencies
├── README.md          # This file
├── .env               # Environment variables (create this)
└── cogs/              # Bot modules/features
    ├── __init__.py
    ├── greetings.py    # Greeting functionality
    ├── utilities.py    # Utility commands
    └── error_handler.py # Error handling
```

## Setup

1. **Clone the repository** (or download the files)

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Create a `.env` file** in the root directory:
   ```
   DISCORD_BOT_TOKEN=your_bot_token_here
   LOG_LEVEL=INFO
   LOG_FILE=bot.log
   ```

4. **Run the bot**:
   ```bash
   python bot.py
   ```

## Commands

### Greeting Commands
- `!greet` - Get a random greeting
- `!greetings` - List all available greetings

### Utility Commands
- `!ping` - Check bot latency
- `!uptime` - Check bot uptime
- `!info` - Display bot information

### Admin Commands (Owner only)
- `!reload <cog_name>` - Reload a specific cog

## Adding New Features

The bot is designed for easy expansion. To add new features:

1. **Create a new cog** in the `cogs/` directory
2. **Follow the cog template**:
   ```python
   from discord.ext import commands
   
   class YourFeature(commands.Cog):
       def __init__(self, bot):
           self.bot = bot
       
       @commands.command()
       async def your_command(self, ctx):
           await ctx.send("Your response")
   
   async def setup(bot):
       await bot.add_cog(YourFeature(bot))
   ```
3. **The bot will automatically load** your new cog on restart

## Configuration

### Environment Variables
- `DISCORD_BOT_TOKEN` - Your Discord bot token (required)
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR) - default: INFO
- `LOG_FILE` - Log file path - default: bot.log

### Constants
Edit `constants.py` to:
- Add new greetings to the `GREETINGS` list
- Add new help messages to the `HELP_MESSAGES` list
- Modify greeting trigger words in `GREETING_WORDS`
- Change the command prefix in `COMMAND_PREFIX`

## Error Handling

The bot includes comprehensive error handling:
- Command errors are logged and users receive friendly error messages
- Bot errors are logged for debugging
- Configuration errors are displayed on startup

## Logging

The bot automatically logs:
- Bot startup and shutdown
- Cog loading/reloading
- Command errors
- System errors

Logs are written to both console and file (default: `bot.log`).

## Contributing

1. Follow the existing code structure
2. Add new features as separate cogs
3. Include proper error handling
4. Document your changes
5. Test thoroughly before submitting

## License

This project is open source. Feel free to modify and distribute as needed.