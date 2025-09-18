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
Catch, collect, and manage your Pokemon in this engaging mini-game! The system features a complete refactored modular architecture with comprehensive Pokemon database.

---

#### 🌿 Basic Pokemon Commands

**Encounter Pokemon:**
- `/encounter` - Encounter a wild Pokemon (5-minute cooldown)
- `!encounter` - Encounter a wild Pokemon (prefix command)
- `!wild` - Encounter a wild Pokemon (alias)
- `!pokemon` - Encounter a wild Pokemon (alias)

**Catch Pokemon:**
- `/catch [ball_type]` - Attempt to catch your currently encountered Pokemon (with dropdown)
- `!catch [ball_type]` - Attempt to catch your currently encountered Pokemon
  - `!catch normal` - Use a normal Pokeball (default)
  - `!catch master` - Use a Master Ball (100% catch rate)

**Wild Pokemon Events:**
- `/wild_catch` - Attempt to catch the current wild Pokemon in #pokemon channel
- `!wild_catch` - Attempt to catch the current wild Pokemon (prefix command)
- `!wcatch` - Attempt to catch wild Pokemon (alias)
- `/wild_status` - Check the status of wild Pokemon spawning
- `!wild_status` - Check wild spawn status (prefix command)
- `!wstatus` - Check wild spawn status (alias)

---

#### 🏆 Leaderboard Commands

**Pokemon Collection Leaderboard:**
- `/leaderboard_pokemon` - View Pokemon collection leaderboard (top 10)
- `!leaderboard_pokemon` - View Pokemon collection leaderboard (prefix command)
- `!lb_pokemon` - Leaderboard alias
- `!pokemon_leaderboard` - Leaderboard alias

**Total Power Leaderboard:**
- `/leaderboard_power` - View total power leaderboard (top 10)
- `!leaderboard_power` - View total power leaderboard (prefix command)
- `!lb_power` - Power leaderboard alias
- `!power_leaderboard` - Power leaderboard alias

**Rarity Score Leaderboard:**
- `/leaderboard_rarity` - View rarity score leaderboard (top 10)
- `!leaderboard_rarity` - View rarity score leaderboard (prefix command)
- `!lb_rarity` - Rarity leaderboard alias
- `!rarity_leaderboard` - Rarity leaderboard alias

**Individual Rankings:**
- `/leaderboard_rank [user]` - Check individual rank in all leaderboards (with user picker)
- `!leaderboard_rank [user]` - Check individual rank in all leaderboards
- `!lb_rank [user]` - Rank lookup alias
- `!rank [user]` - Rank lookup alias

**Leaderboard Examples:**
- `/leaderboard_pokemon` or `!leaderboard_pokemon` - View top 10 Pokemon collectors
- `/leaderboard_power` or `!lb_power` - View top 10 by total power
- `/leaderboard_rarity` or `!rarity_leaderboard` - View top 10 by rarity score
- `/leaderboard_rank @username` or `!rank @username` - Check someone's rankings
- `/leaderboard_rank` or `!rank` - Check your own rankings

**Leaderboard Scoring:**
- **Pokemon Count:** Total unique Pokemon caught
- **Total Power:** Sum of Attack + Defense + HP for all Pokemon
- **Rarity Score:** Points based on Pokemon rarity (Mythical=150pts, Legendary=100pts, Ultra Rare=75pts, Rare=50pts, Uncommon=25pts, Common=0pts)

---

#### 📖 Collection Commands

**View Collections:**
- `/collection [user]` - View your Pokemon collection or another user's (with user picker)
- `!pokemon_list [user]` - View your Pokemon collection or another user's
- `!pokedex [user]` - View Pokemon collection (alias)
- `!collection [user]` - View Pokemon collection (alias)

**Statistics & Information:**
- `/pokemon_stats` - View your Pokemon game statistics
- `!pokemon_stats` - View your Pokemon game statistics (prefix command)
- `!stats` - View your statistics (alias)
- `/inventory` - View your Pokemon inventory and items
- `!inventory` - View your Pokemon inventory (prefix command)
- `!inv` - View inventory (alias)
- `!bag` - View inventory (alias)

**Pokemon Details:**
- `/pokemon_info <pokemon_identifier>` - View detailed info about a specific Pokemon (with autocomplete)
- `!pokemon_info <name/id>` - View detailed info about a specific Pokemon in your collection
- `!pinfo <name/id>` - View Pokemon details (alias)
- `!pokemon_detail <name/id>` - View Pokemon details (alias)

**Examples:**
- `/pokemon_info Pikachu` or `!pokemon_info Pikachu` - View your Pikachu's details
- `/pokemon_info #5` or `!pinfo #5` - View details of Pokemon #5 in your collection
- `/collection @username` or `!collection @username` - View another user's collection

---

#### 🔧 Admin Commands
*These commands require admin permissions*

**Database Management:**
- `/pokemon_admin` - View Pokemon database statistics and management panel
- `!pokemon_admin` - View Pokemon database (prefix command)
- `!padmin` - Admin panel (alias)

**Player Management:**
- `/give_pokeball <user> <ball_type> <count>` - Give pokeballs to a user (with dropdowns)
- `!give_pokeball <user> <ball_type> <count>` - Give pokeballs to a user
- `!give_ball <user> <ball_type> <count>` - Give pokeballs (alias)
- `!pokeball_admin <user> <ball_type> <count>` - Give pokeballs (alias)

**Wild Spawn Control:**
- `/force_wild_spawn` - Manually trigger a wild Pokemon spawn
- `!force_wild_spawn` - Manually trigger a wild Pokemon spawn (prefix command)
- `!fws` - Force wild spawn (alias)

**Debug & Troubleshooting:**
- `/debug_channels` - Check available channels and bot permissions
- `!debug_channels` - Check available channels (prefix command)
- `!dchannels` - Debug channels (alias)

**Admin Examples:**
- `/give_pokeball @username normal 10` or `!give_pokeball @username normal 10` - Give 10 normal pokeballs
- `/give_pokeball @username master 1` or `!give_pokeball @username master 1` - Give 1 master ball
- `/force_wild_spawn` or `!force_wild_spawn` - Trigger immediate wild spawn

---

#### 🎮 Game Features

**Modern Command Support:**
- **Slash Commands:** Full support with autocomplete, dropdowns, and parameter hints
- **Prefix Commands:** Traditional `!command` support with all aliases maintained
- **Interactive Elements:** Ball type dropdowns, user pickers, and intelligent autocomplete
- **Backward Compatibility:** All existing prefix commands continue to work

**Starting Inventory:**
- All new players begin with 5 normal Pokeballs
- Master Balls available through admin distribution

**Pokemon Database:**
- **1000+ Pokemon** from all 9 generations with complete stats and images
- **Real Pokemon Data:** Official sprites, artwork, descriptions, and base stats
- **Generation Coverage:** Complete coverage from Kanto to Paldea

**Pokemon Rarities & Distribution:**
- **Common (60%):** Easily encountered Pokemon
- **Uncommon (30%):** Moderately rare Pokemon  
- **Rare (8%):** Hard to find Pokemon
- **Legendary (2%):** Extremely rare legendary Pokemon

**Encounter System:**
- **Personal Encounters:** 5-minute cooldown between personal encounters
- **Wild Spawns:** Global spawns every 30 minutes in #pokemon channel
- **Catch Rates:** Intelligently calculated based on Pokemon stats and rarity
- **Two Ball Types:** Normal Pokeballs (variable rate) vs Master Balls (100% rate)

**Collection Features:**
- **Unique Collection IDs:** Each caught Pokemon gets a unique ID in your collection
- **Detailed Tracking:** Caught date, ball type used, source (encounter vs wild)
- **Complete Pokemon Data:** Full stats, types, generation, descriptions, and images
- **Collection Statistics:** Track total caught, encounter rate, rarity breakdown

**Wild Spawn System:**
- **Automatic Spawns:** Every 30 minutes in designated #pokemon channel
- **Competition:** First trainer to successfully catch wins the Pokemon
- **Common/Uncommon Only:** Wild spawns feature common and uncommon Pokemon
- **Global Announcements:** Rich embeds with Pokemon details and catch instructions

---

#### 📊 Database Coverage

**Generation Breakdown:**
- **Generation 1 (Kanto):** Classic 151 Pokemon including all starters and legendaries
- **Generation 2 (Johto):** Dark/Steel types, legendary beasts, Ho-Oh, Lugia
- **Generation 3 (Hoenn):** Abilities system, weather legendaries, Rayquaza
- **Generation 4 (Sinnoh):** Physical/special split, Dialga, Palkia, Giratina
- **Generation 5 (Unova):** Large regional dex, Reshiram, Zekrom, Kyurem
- **Generation 6 (Kalos):** Fairy type introduction, Xerneas, Yveltal
- **Generation 7 (Alola):** Z-moves, Ultra Necrozma, Tapu guardians
- **Generation 8 (Galar):** Dynamax system, Eternatus, Zacian, Zamazenta
- **Generation 9 (Paldea):** Latest generation, Koraidon, Miraidon, new starters

**Complete Coverage Includes:**
- All starter evolution lines from every generation
- All pseudo-legendary Pokemon (Dragonite, Tyranitar, Metagross, etc.)
- All major legendary and mythical Pokemon
- Popular fan-favorites and competitive Pokemon
- Complete type coverage including all 18 Pokemon types

---

#### 💡 Usage Examples

**Basic Gameplay:**
```
/encounter            # Find a wild Pokemon (slash command)
!encounter            # Find a wild Pokemon (prefix command)
/catch normal         # Catch with normal Pokeball (with dropdown)
!catch normal         # Catch with normal Pokeball (prefix)
/catch master         # Catch with Master Ball (100% rate)
!catch master         # Catch with Master Ball (prefix)
/collection           # View your Pokemon collection
!collection           # View your collection (prefix)
/pokemon_stats        # Check your statistics
!stats                # Check your statistics (prefix)
```

**Wild Pokemon Events:**
```
/wild_status          # Check if wild Pokemon is available
!wild_status          # Check wild status (prefix command)
/wild_catch           # Attempt to catch wild Pokemon (in #pokemon channel)
!wild_catch           # Attempt to catch wild Pokemon (prefix)
```

**Collection Management:**
```
/inventory            # View your items and collection summary
!inventory            # View inventory (prefix command)
/pokemon_info Charizard    # View your Charizard's details (with autocomplete)
!pokemon_info Charizard   # View Charizard details (prefix)
/pokemon_info #1      # View details of Pokemon #1 in collection
!pinfo #1             # View Pokemon #1 details (prefix alias)
/collection @friend   # View a friend's collection (with user picker)
!collection @friend   # View friend's collection (prefix)
```

**Leaderboards:**
```
/leaderboard_pokemon     # View top 10 Pokemon collectors
!leaderboard_pokemon     # View Pokemon leaderboard (prefix)
/leaderboard_power       # View top 10 by total power
!lb_power                # View power leaderboard (prefix alias)
/leaderboard_rarity      # View top 10 by rarity score
!rarity_leaderboard      # View rarity leaderboard (prefix alias)
/leaderboard_rank @user  # Check someone's rank in all leaderboards
!rank @user              # Check user's rank (prefix alias)
/leaderboard_rank        # Check your own rankings
!rank                    # Check your own rankings (prefix)
```

**Admin Operations:**
```
/pokemon_admin              # View database statistics
!pokemon_admin              # View database stats (prefix)
/give_pokeball @user normal 5    # Give 5 normal balls (with dropdowns)
!give_pokeball @user normal 5    # Give 5 normal balls (prefix)
/give_pokeball @user master 1    # Give 1 master ball
!give_pokeball @user master 1    # Give 1 master ball (prefix)
/force_wild_spawn          # Trigger immediate wild spawn
!force_wild_spawn          # Trigger wild spawn (prefix)
/debug_channels            # Debug channel permissions
!debug_channels            # Debug channels (prefix)
```

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
| **Pokemon** | `/encounter`, `/catch`, `/wild_catch`, `/collection`, `/pokemon_stats`, `/inventory`, `/pokemon_info` | `!encounter`, `!catch`, `!wild_catch`, `!collection`, `!stats`, `!inventory`, `!pokemon_info` |
| **Pokemon Leaderboards** | `/leaderboard_pokemon`, `/leaderboard_power`, `/leaderboard_rarity`, `/leaderboard_rank` | `!leaderboard_pokemon`, `!leaderboard_power`, `!leaderboard_rarity`, `!leaderboard_rank`, `!lb_pokemon`, `!lb_power`, `!lb_rarity`, `!rank` |
| **Pokemon Admin** | `/pokemon_admin`, `/give_pokeball`, `/force_wild_spawn`, `/debug_channels` | `!pokemon_admin`, `!give_pokeball`, `!force_wild_spawn`, `!debug_channels` |
| **Greetings** | - | `!greet`, `!greetings` |
| **Utilities** | - | `!info`, `!ping`, `!uptime` |
| **Admin** | - | `!reload` |

---

*Last Updated: December 27, 2024*