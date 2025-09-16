# Legion Discord Bot

A simple Discord bot that responds to "hi" with random greetings in different languages from around the world! 🌍

## Features

- Responds to "hi" messages with random greetings in 20+ languages
- Includes greetings in English, Spanish, French, German, Italian, Portuguese, Swedish, Dutch, Russian, Japanese, Korean, Chinese, Arabic, Hindi, Urdu, Zulu, Swahili, Hebrew, Greek, and Thai
- Additional commands for manual greeting requests
- Easy to set up and customize

## Setup Instructions

### 1. Prerequisites
- Python 3.8 or higher
- A Discord account
- Basic knowledge of creating Discord applications

### 2. Create a Discord Bot
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section in the left sidebar
4. Click "Add Bot"
5. Copy the bot token (you'll need this later)
6. Under "Privileged Gateway Intents", enable "Message Content Intent"

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure the Bot
1. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```
2. Edit the `.env` file and replace `your_bot_token_here` with your actual bot token

### 5. Invite the Bot to Your Server
1. In the Discord Developer Portal, go to "OAuth2" > "URL Generator"
2. Select scopes: `bot`
3. Select bot permissions: `Send Messages`, `Read Message History`
4. Use the generated URL to invite the bot to your server

### 6. Run the Bot
```bash
python bot.py
```

## Usage

### Automatic Responses
- Simply type "hi" in any channel where the bot has access
- The bot will respond with a random greeting in a different language

### Commands
- `!greet` - Get a random greeting manually
- `!greetings` - See all available greetings the bot knows

## Supported Languages

The bot knows greetings in the following languages:
- English, Spanish, French, German, Italian
- Portuguese, Swedish, Dutch, Russian
- Japanese, Korean, Chinese, Arabic
- Hindi, Urdu, Zulu, Swahili
- Hebrew, Greek, Thai

## File Structure

```
legion_discord_bot/
├── bot.py              # Main bot code
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables template
├── .env              # Your actual environment variables (create this)
└── README.md         # This file
```

## Customization

To add more greetings or languages, edit the `GREETINGS` list in `bot.py`:

```python
GREETINGS = [
    "Your greeting! 👋",  # Your language
    # ... add more greetings here
]
```

## Troubleshooting

### Bot doesn't respond
- Make sure the bot has "Message Content Intent" enabled in Discord Developer Portal
- Check that the bot has permission to read and send messages in the channel
- Verify your bot token is correct in the `.env` file

### Import errors
- Make sure you've installed all requirements: `pip install -r requirements.txt`
- Check that you're using Python 3.8 or higher

## Contributing

Feel free to add more greetings in different languages or improve the bot's functionality!

## License

This project is open source and available under the MIT License.