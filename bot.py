import discord
from discord.ext import commands
import random
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Random greetings in different languages
GREETINGS = [
    "Hello there",  # English
    "Hey there",    # English casual
    "Hi",           # English simple
    "Good day",     # English formal
    "Greetings",    # English formal
    "What's up",    # English casual
    "Howdy",        # English casual
    "नमस्ते",        # Hindi
    "नमस्कार",       # Hindi formal
    "आदाब",         # Hindi/Urdu
    "राम राम",       # Hindi traditional
    "जय हिंद",       # Hindi patriotic
    "Hola",         # Spanish
    "Bonjour",      # French
    "Guten Tag",    # German
    "Ciao",         # Italian
    "Olá",          # Portuguese
    "Hej",          # Swedish
    "Hallo",        # Dutch
    "Привет",       # Russian
    "こんにちは",      # Japanese
    "안녕하세요",      # Korean
    "你好",          # Chinese
    "مرحبا",        # Arabic
    "Salaam",       # Urdu
    "Sawubona",     # Zulu
    "Jambo",        # Swahili
    "Shalom",       # Hebrew
    "Γεια σας",      # Greek
    "สวัสดี",        # Thai
    "Xin chào",     # Vietnamese
    "Zdravo",       # Serbian
    "Halo",         # Indonesian
    "Kumusta"       # Filipino
]

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is ready and listening for messages!')

@bot.event
async def on_message(message):
    # Don't respond to the bot's own messages
    if message.author == bot.user:
        return
    
    # Check if the message content is a greeting (case insensitive)
    greeting_words = ['hi', 'hello', 'hey', 'hola', 'bonjour', 'hallo', 'ciao']
    if message.content.lower().strip() in greeting_words:
        # Select a random greeting
        greeting = random.choice(GREETINGS)
        await message.channel.send(f"{greeting} {message.author.mention}!")
    
    # Process other commands
    await bot.process_commands(message)

@bot.command(name='greet')
async def greet_command(ctx):
    """Command to get a random greeting"""
    greeting = random.choice(GREETINGS)
    await ctx.send(f"{greeting} {ctx.author.mention}")

@bot.command(name='greetings')
async def list_greetings(ctx):
    """Command to see all available greetings"""
    greetings_text = "Here are all the greetings I know:\n" + "\n".join(GREETINGS)
    await ctx.send(greetings_text)

# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found in environment variables!")
        print("Please create a .env file with your bot token.")
        exit(1)
    
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("Error: Invalid bot token!")
    except Exception as e:
        print(f"Error starting bot: {e}")