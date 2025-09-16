"""
Constants for the Legion Discord Bot
Contains all static data like greetings, help messages, and other configuration constants.
"""

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

# Help messages when bot is mentioned
HELP_MESSAGES = [
    # English help messages
    "How can I help you today?",
    "What can I do for you?",
    "Need assistance with something?",
    "How may I assist you?",
    "What would you like to know?",
    # Hindi help messages
    "आज मैं आपकी कैसे मदद कर सकता हूँ?",
    "मैं आपके लिए क्या कर सकता हूँ?",
    "क्या आपको किसी चीज़ में सहायता चाहिए?",
    "मैं आपकी कैसे सेवा कर सकता हूँ?",
    "आप क्या जानना चाहते हैं?"
]

# Greeting words that trigger greeting responses
GREETING_WORDS = ['hi', 'hello', 'hey', 'hola', 'bonjour', 'hallo', 'ciao']

# Bot command prefix
COMMAND_PREFIX = '!'