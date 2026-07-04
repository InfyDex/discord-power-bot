"""Music cog entry point. Logic lives in music_system/ — this file just satisfies
bot.py's flat cogs/*.py loader (see load_cogs() in bot.py).
"""
from .music_system.cog import setup  # noqa: F401
