# Legion Discord Bot

A multilingual Discord bot with a modular architecture designed for easy expansion and maintenance.

## Features

- **Multilingual Greetings**: Supports greetings in 30+ languages including English, Hindi, Spanish, French, German, Japanese, Arabic, and many more
- **Smart Mention Response**: Responds helpfully when mentioned
- **Game Commands**: Interactive games like dice rolling and coin flipping with both slash (/) and prefix (!) commands
- **Modern Slash Commands**: Full support for Discord's slash command system with autocomplete and descriptions
- **Consistent Embed Responses**: Professional, uniform embed formatting across all bot responses
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
├── COMMANDS.md        # Complete commands reference
├── .env               # Environment variables (create this)
└── cogs/              # Bot modules/features
    ├── __init__.py
    ├── greetings.py    # Greeting functionality
    ├── games.py        # Game commands (dice, coin flip)
    ├── utilities.py    # Utility commands and embed utilities
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

📋 **For a complete list of all available commands, see [COMMANDS.md](COMMANDS.md)**

The bot supports both modern slash commands (`/command`) and traditional prefix commands (`!command`). Key features include:

- **Game Commands**: Dice rolling, coin flipping
- **Greeting Commands**: Multilingual greetings and responses  
- **Utility Commands**: Bot info, ping, uptime
- **Admin Commands**: Cog management (owner only)

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
4. **Update documentation** by adding your new commands to `COMMANDS.md`

## Music

YouTube playback via `yt-dlp` + FFmpeg. Requires FFmpeg installed and on PATH (`choco install ffmpeg` on Windows).

### Commands

| Slash | Prefix | Description |
|---|---|---|
| `/play <query>` | `!play` / `!p` | Play a song/URL, or queue if already playing (supports playlists) |
| `/search <query>` | — | Search YouTube, pick a result from a dropdown to queue |
| `/skip` | `!skip` / `!s` | Skip the current song |
| `/pause` | — | Pause playback |
| `/resume` | — | Resume playback |
| `/stop` | — | Stop, clear queue, disconnect |
| `/queue` | — | Show now playing + up next |
| `/nowplaying` | — | Show current song |
| `/clear` | `!clear` / `!c` | Clear the queue |
| — | `!remove <pos>` / `!rm` | Remove one song from the queue by position |
| `/shuffle` | — | Shuffle the queue |
| `/loop <off\|track\|queue>` | — | Set loop mode |
| `/autoplay` | — | Toggle auto-queueing related songs (YouTube Mix) when the queue empties |
| `/volume <0-200>` | — | Set playback volume % |
| — | `!testmusic` | Check PyNaCl / yt-dlp / FFmpeg / cookie status |

### YouTube cookies

YouTube blocks download requests from server IPs (VPS, cloud hosts) with a 403 or a
"Sign in to confirm you're not a bot" error unless the request carries a logged-in
session's cookies. On a home/residential IP this usually isn't needed.

**Get `cookies.txt`:**
1. Log into youtube.com in your browser.
2. Export cookies with a browser extension, e.g. "Get cookies.txt LOCALLY" (Chrome/Firefox). Must be Netscape cookie file format.
3. Use one of the options below to give it to the bot — pick whichever fits how you run/deploy it.

**Where to put it — pick one:**

| Method | How | When to use |
|---|---|---|
| File in bot root | Save as `cookies.txt` next to `bot.py` | Simplest — running the bot locally or on a VPS you control |
| `YOUTUBE_COOKIES_FILE` | Set in `.env` to an explicit path, e.g. `YOUTUBE_COOKIES_FILE=/secure/path/cookies.txt` | Cookie file lives outside the repo dir |
| `YOUTUBE_COOKIES_B64` | Base64-encode the file and paste into `.env`: `YOUTUBE_COOKIES_B64=$(base64 -w0 cookies.txt)` | Host with no persistent filesystem / secrets injected as env vars only (Railway, Heroku, etc.) |
| `COOKIES_FROM_BROWSER` | Set in `.env` to `chrome`, `firefox`, `edge`, etc. (add `:ProfileName` for a specific profile) | Bot runs on the **same machine** as the logged-in browser — local dev only |

Priority if multiple are set: `YOUTUBE_COOKIES_B64` > `YOUTUBE_COOKIES_FILE` > `cookies.txt` in bot root > `COOKIES_FROM_BROWSER`.

`cookies.txt` contains live session tokens — never commit it (already in `.gitignore`), never share it.

## Configuration

### Environment Variables
- `DISCORD_BOT_TOKEN` - Your Discord bot token (required)
- `DISCORD_COMMAND_PREFIX` - Set the bot's command prefix (default is `!`). Example: `DISCORD_COMMAND_PREFIX=?`
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR) - default: INFO
- `LOG_FILE` - Log file path - default: bot.log
- `YOUTUBE_COOKIES_B64` / `YOUTUBE_COOKIES_FILE` / `COOKIES_FROM_BROWSER` - YouTube cookie auth, see [Music](#music)

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