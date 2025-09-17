# Legion Discord Bot - Commands Reference

This document contains all available commands for the Legion Discord Bot. Commands are organized by category for easy reference.

## 📋 Command Types

The bot supports both modern **Slash Commands** (`/command`) and traditional **Prefix Commands** (`!command`). You can use either type based on your preference.

---

## 🎮 Game Commands

### Coin Flip
Flip a virtual coin and get heads or tails.

**Slash Command:**
- `/flip` - Flip a coin

**Prefix Commands:**
- `!flip` - Flip a coin
- `!coin` - Flip a coin (alias)
- `!coinflip` - Flip a coin (alias)

**Example:** `/flip` or `!flip`

---

### Dice Rolling
Roll dice using standard tabletop gaming notation.

**Slash Command:**
- `/roll [dice_notation]` - Roll dice with specified notation

**Prefix Commands:**
- `!roll [dice_notation]` - Roll dice with specified notation
- `!dice [dice_notation]` - Roll dice (alias)
- `!r [dice_notation]` - Roll dice (short alias)

**Dice Notation Examples:**
- `1d6` or `d6` - Roll a single 6-sided die
- `2d20` - Roll two 20-sided dice
- `3d8` - Roll three 8-sided dice
- `d100` - Roll a 100-sided die
- `4d6` - Roll four 6-sided dice

**Examples:** 
- `/roll 2d20` or `!roll 2d20`
- `/roll d100` or `!dice d100`
- `/roll` or `!r` (defaults to 1d6)

**Limits:**
- Number of dice: 1-20
- Dice sides: 2-1000

---

### Pokemon Game
Catch, collect, and manage your Pokemon in this engaging mini-game!

**Prefix Commands:**
- `!encounter` - Encounter a wild Pokemon (5-minute cooldown)
- `!wild` - Encounter a wild Pokemon (alias)
- `!pokemon` - Encounter a wild Pokemon (alias)
- `!catch` - Attempt to catch the currently encountered Pokemon
- `!pokemon_list` - View your Pokemon collection
- `!pokedex` - View your Pokemon collection (alias)
- `!collection` - View your Pokemon collection (alias)
- `!pokemon_stats` - View your Pokemon game statistics
- `!stats` - View your Pokemon game statistics (alias)
- `!pokemon_info <name/id>` - View detailed info about a specific Pokemon
- `!pinfo <name/id>` - View detailed info about a specific Pokemon (alias)
- `!pokemon_detail <name/id>` - View detailed info about a specific Pokemon (alias)

**Game Features:**
- **Starting Inventory:** All players begin with 5 normal Pokeballs
- **Pokemon Database:** 78+ Pokemon from Generations 1-3 with complete stats and images
- **Pokemon Rarities:** Common (45%), Uncommon (35%), Rare (15%), Legendary (5%)
- **Encounter Cooldown:** 5 minutes between Pokemon encounters
- **Catch Rates:** Intelligently calculated based on Pokemon base stats and rarity
- **Collection Tracking:** Track all caught Pokemon with unique IDs and detailed stats
- **Statistics:** Monitor encounters, catch rate, and collection progress
- **Pokemon Images:** High-quality official artwork and sprites from GitHub repository

**Pokemon Available:**
- **Generation 1 (Kanto):** 43 Pokemon including starters, legendaries, and classics
- **Generation 2 (Johto):** 19 Pokemon including new starters and legendary beasts
- **Generation 3 (Hoenn):** 16 Pokemon including Hoenn starters and weather legendaries
- **Rarity Distribution:** Automatically calculated based on base stat totals
- **Starter Pokemon:** All region starters (Bulbasaur line, Charmander line, Squirtle line, Chikorita line, Cyndaquil line, Totodile line, Treecko line, Torchic line, Mudkip line)
- **Legendary Pokemon:** Articuno, Zapdos, Moltres, Mewtwo, Mew, Raikou, Entei, Suicune, Lugia, Ho-Oh, Celebi, Latias, Latios, Kyogre, Groudon, Rayquaza, Jirachi, Deoxys

**Examples:** 
- `!encounter` - Find a wild Pokemon
- `!catch` - Try to catch the encountered Pokemon
- `!pokedex` - See your collection
- `!stats` - Check your Pokemon statistics
- `!pinfo Pikachu` - View detailed info about your Pikachu
- `!pokemon_info #5` - View info about Pokemon #5 in your collection

---

## 👋 Greeting Commands

### Random Greeting
Get a random greeting from the bot's multilingual collection.

**Command:**
- `!greet` - Get a random greeting

**Example:** `!greet`

---

### List All Greetings
See all available greetings in the bot's database.

**Command:**
- `!greetings` - Display all available greetings

**Example:** `!greetings`

---

### Automatic Greetings
The bot automatically responds to greeting messages and mentions.

**Triggers:**
- Send any greeting word (hello, hi, hey, etc.)
- Mention the bot with no other text

**Supported Greeting Words:**
- English: hello, hi, hey, greetings, good morning, good afternoon, good evening
- And many more in 30+ languages!

---

## 🔧 Utility Commands

### Bot Information
Display comprehensive information about the bot.

**Command:**
- `!info` - Show bot statistics and system information

**Example:** `!info`

**Displays:**
- Bot statistics (servers, users, latency)
- System information (CPU, memory usage)
- Bot version and ID

---

### Ping Test
Check the bot's response time and connection status.

**Command:**
- `!ping` - Test bot latency

**Example:** `!ping`

---

### Uptime
Check how long the bot has been running.

**Command:**
- `!uptime` - Show bot uptime

**Example:** `!uptime`

---

## ⚙️ Admin Commands

These commands are restricted to the bot owner only.

### Reload Cog
Reload a specific bot module without restarting the entire bot.

**Command:**
- `!reload <cog_name>` - Reload a specific cog

**Example:** `!reload games`

**Available Cogs:**
- `games` - Game commands (flip, roll)
- `greetings` - Greeting functionality
- `utilities` - Utility commands
- `error_handler` - Error handling

---

## 🆘 Error Handling

The bot provides helpful error messages for common issues:

- **Invalid dice notation** - Guidance on proper format
- **Permission errors** - Clear explanation of missing permissions
- **Cooldown messages** - Information about command cooldowns
- **Missing arguments** - Helpful hints about required parameters

All error messages use professional embeds and mention the user who triggered them.

---

## 📝 Notes

### Slash Commands vs Prefix Commands
- **Slash Commands** (`/command`) provide autocomplete, parameter hints, and a modern Discord experience
- **Prefix Commands** (`!command`) offer traditional bot interaction for users who prefer the classic style
- Both command types provide identical functionality

### Mentions and Responses
- All bot responses mention the user who initiated the command
- Embed footers show "Requested by @username"
- Error messages are personalized and user-friendly

### Adding New Commands
This document will be updated whenever new commands are added to the bot. Check back regularly for new features!

---

## 🎯 Quick Reference

| Category | Slash Commands | Prefix Commands |
|----------|---------------|-----------------|
| **Games** | `/flip`, `/roll` | `!flip`, `!coin`, `!roll`, `!dice`, `!r` |
| **Pokemon** | - | `!encounter`, `!catch`, `!pokedex`, `!stats` |
| **Greetings** | - | `!greet`, `!greetings` |
| **Utilities** | - | `!info`, `!ping`, `!uptime` |
| **Admin** | - | `!reload` |

---

*Last Updated: September 17, 2025*