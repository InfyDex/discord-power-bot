"""
Pokemon Game cog for the Legion Discord Bot
Handles Pokemon encounters, catching, and collection management.
"""

import discord
from discord.ext import commands, tasks
import random
import json
import os
from datetime import datetime, timedelta
from .utilities import EmbedUtils
import config
from config import Config

class Pokemon(commands.Cog):
    """Cog for Pokemon game functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "pokemon_data.json"
        self.pokemon_db_file = "pokemon_master_database.json"
        self.player_data = self.load_player_data()
        self.pokemon_database = self.load_pokemon_database()
        self.wild_spawn_data = self.load_wild_spawn_data()
        self.spawn_task = None
        self._spawn_task_started = False
        
        # Don't start the spawn task immediately - wait for bot to be ready
    
    def load_wild_spawn_data(self):
        """Load wild spawn data from JSON file"""
        spawn_file = "wild_spawn_data.json"
        if os.path.exists(spawn_file):
            try:
                with open(spawn_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {"last_spawn": None, "current_wild": None, "spawn_channel": "pokemon"}
        return {"last_spawn": None, "current_wild": None, "spawn_channel": "pokemon"}
    
    def save_wild_spawn_data(self):
        """Save wild spawn data to JSON file"""
        spawn_file = "wild_spawn_data.json"
        try:
            with open(spawn_file, 'w') as f:
                json.dump(self.wild_spawn_data, f, indent=2)
        except Exception as e:
            print(f"Error saving wild spawn data: {e}")
    
    def start_wild_spawn_task(self):
        """Start the background task for wild Pokemon spawning"""
        @tasks.loop(minutes=30)
        async def wild_spawn_loop():
            await self.spawn_wild_pokemon()
        
        self.spawn_task = wild_spawn_loop
        self.spawn_task.start()
    
    def get_common_uncommon_pokemon(self):
        """Get a random Pokemon that is Common or Uncommon rarity only"""
        common_uncommon_pokemon = [
            (pokemon_id, pokemon_data) for pokemon_id, pokemon_data in self.pokemon_database.items() 
            if pokemon_data['rarity'] in ['Common', 'Uncommon']
        ]
        
        if not common_uncommon_pokemon:
            return None
        
        # Weight towards common (70% common, 30% uncommon)
        common_pokemon = [(pid, pdata) for pid, pdata in common_uncommon_pokemon if pdata['rarity'] == 'Common']
        uncommon_pokemon = [(pid, pdata) for pid, pdata in common_uncommon_pokemon if pdata['rarity'] == 'Uncommon']
        
        chosen_pokemon = None
        if random.random() < 0.7 and common_pokemon:
            chosen_pokemon = random.choice(common_pokemon)
        elif uncommon_pokemon:
            chosen_pokemon = random.choice(uncommon_pokemon)
        else:
            chosen_pokemon = random.choice(common_uncommon_pokemon)
        
        if chosen_pokemon:
            pokemon_id, pokemon_data = chosen_pokemon
            # Add the ID to the pokemon data
            pokemon_with_id = pokemon_data.copy()
            pokemon_with_id['id'] = int(pokemon_id)
            return pokemon_with_id
        
        return None
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener that triggers when the bot is ready and connected to guilds"""
        # Only start the spawn task once, after the bot is connected
        if not self._spawn_task_started and len(self.bot.guilds) > 0:
            self.start_wild_spawn_task()
            self._spawn_task_started = True
            print(f"Wild Pokemon spawn task started! Bot is connected to {len(self.bot.guilds)} guild(s)")
    
    async def spawn_wild_pokemon(self):
        """Spawn a wild Pokemon in the designated channel"""
        try:
            # Find the pokemon channel with enhanced debugging
            channel = None
            target_channel_name = self.wild_spawn_data["spawn_channel"]
            
            print(f"Looking for channel named: '{target_channel_name}'")
            print(f"Bot is in {len(self.bot.guilds)} guild(s)")
            
            for guild in self.bot.guilds:
                print(f"Searching in guild: {guild.name}")
                
                # List all text channels for debugging
                text_channels = [ch.name for ch in guild.text_channels]
                print(f"Available text channels: {text_channels}")
                
                # Try to find the channel
                channel = discord.utils.get(guild.text_channels, name=target_channel_name)
                if channel:
                    print(f"Found channel: {channel.name} (ID: {channel.id})")
                    break
                else:
                    # Try case-insensitive search
                    for ch in guild.text_channels:
                        if ch.name.lower() == target_channel_name.lower():
                            channel = ch
                            print(f"Found channel with case-insensitive match: {ch.name} (ID: {ch.id})")
                            break
                    if channel:
                        break
            
            if not channel:
                # Don't spam the console on every failed attempt
                # Only log if this is the first few attempts or intermittently
                if not hasattr(self, '_spawn_error_count'):
                    self._spawn_error_count = 0
                
                self._spawn_error_count += 1
                
                # Log error every 10 attempts to avoid spam
                if self._spawn_error_count <= 3 or self._spawn_error_count % 10 == 0:
                    print(f"Pokemon spawn channel '{target_channel_name}' not found in any guild! (Attempt {self._spawn_error_count})")
                    if self._spawn_error_count <= 3:
                        print("Please make sure:")
                        print("1. The bot has access to the channel")
                        print("2. The channel name is exactly 'pokemon' (lowercase)")
                        print("3. The bot has 'View Channels' and 'Send Messages' permissions")
                return
            
            # Reset error counter on successful channel find
            if hasattr(self, '_spawn_error_count'):
                self._spawn_error_count = 0
            
            # Get a common or uncommon Pokemon
            pokemon = self.get_common_uncommon_pokemon()
            if not pokemon:
                print("No common/uncommon Pokemon found for spawning!")
                return
            
            # Store the wild Pokemon data
            self.wild_spawn_data["current_wild"] = {
                "pokemon": pokemon,
                "spawn_time": datetime.now().isoformat(),
                "caught_by": None,
                "channel_id": channel.id
            }
            self.wild_spawn_data["last_spawn"] = datetime.now().isoformat()
            self.save_wild_spawn_data()
            
            # Create spawn embed
            embed = discord.Embed(
                title=f"� A Wild {pokemon['name']} Appeared!",
                description=f"A wild **{pokemon['name']}** has appeared! First trainer to catch it wins!\n\n**Type `!wild_catch` to attempt capture**\n\n*{pokemon['description']}*",
                color=self.get_type_color(pokemon['types'])
            )
            
            # Add Pokemon image
            embed.set_image(url=pokemon['image_url'])
            embed.set_thumbnail(url=pokemon['sprite_url'])
            
            # Format types
            type_text = " / ".join(pokemon['types'])
            embed.add_field(name="Type", value=f"{type_text}", inline=True)
            embed.add_field(name="Rarity", value=f"{pokemon['rarity']}", inline=True)
            embed.add_field(name="Catch Rate", value=f"{int(pokemon['catch_rate'] * 100)}%", inline=True)
            
            # Add Pokedex and generation info
            embed.add_field(name="Pokedex #", value=f"#{pokemon['id']}", inline=True)
            embed.add_field(name="Generation", value=f"Gen {pokemon['generation']}", inline=True)
            embed.add_field(name="Total Stats", value=f"{pokemon['stats'].get('total', sum(pokemon['stats'].values()))}", inline=True)
            
            # Clean stats display
            stats = pokemon['stats']
            stats_text = f"**HP:** {stats['hp']} | **ATK:** {stats['attack']} | **DEF:** {stats['defense']}\n**SP.ATK:** {stats['sp_attack']} | **SP.DEF:** {stats['sp_defense']} | **SPD:** {stats['speed']}"
            embed.add_field(name="📊 Base Stats", value=stats_text, inline=False)
            
            # Simple competition info
            embed.add_field(
                name="🎯 How to Catch", 
                value="Type `!wild_catch` to attempt capture!\nFirst successful trainer wins this Pokemon.", 
                inline=False
            )
            
            # Simple footer
            embed.set_footer(text=f"Wild Pokemon Event • Gen {pokemon['generation']} • Next spawn in 30 minutes")
            embed.set_author(name="Legion Pokemon", icon_url="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/poke-ball.png")
            
            await channel.send(embed=embed)
            
        except Exception as e:
            print(f"Error in wild spawn: {e}")
    
    def load_pokemon_database(self):
        """Load the Pokemon database from JSON file"""
        try:
            with open(self.pokemon_db_file, 'r', encoding='utf-8') as f:
                db = json.load(f)
                # Convert string keys to integers
                return {int(k): v for k, v in db.items()}
        except FileNotFoundError:
            print(f"Pokemon database file {self.pokemon_db_file} not found!")
            return {}
        except json.JSONDecodeError:
            print(f"Error decoding {self.pokemon_db_file}")
            return {}
    
    def get_pokemon_by_id(self, pokemon_id):
        """Get Pokemon data by ID"""
        return self.pokemon_database.get(pokemon_id)
    
    def get_pokemon_by_name(self, name):
        """Get Pokemon data by name"""
        for pokemon in self.pokemon_database.values():
            if pokemon['name'].lower() == name.lower():
                return pokemon
        return None
    
    def get_type_color(self, pokemon_types):
        """Get Discord embed color based on primary Pokemon type"""
        type_colors = {
            "Normal": 0xA8A878,
            "Fire": 0xF08030,
            "Water": 0x6890F0,
            "Electric": 0xF8D030,
            "Grass": 0x78C850,
            "Ice": 0x98D8D8,
            "Fighting": 0xC03028,
            "Poison": 0xA040A0,
            "Ground": 0xE0C068,
            "Flying": 0xA890F0,
            "Psychic": 0xF85888,
            "Bug": 0xA8B820,
            "Rock": 0xB8A038,
            "Ghost": 0x705898,
            "Dragon": 0x7038F8,
            "Dark": 0x705848,
            "Steel": 0xB8B8D0,
            "Fairy": 0xEE99AC
        }
        primary_type = pokemon_types[0] if pokemon_types else "Normal"
        return type_colors.get(primary_type, 0x000000)
    
    def get_random_pokemon_by_rarity(self):
        """Get a random Pokemon based on rarity weights"""
        rarity_weights = {
            "Common": 0.60,
            "Uncommon": 0.30, 
            "Rare": 0.08,
            "Legendary": 0.02
        }
        
        # Choose rarity based on weights
        rarities = list(rarity_weights.keys())
        weights = list(rarity_weights.values())
        chosen_rarity = random.choices(rarities, weights=weights)[0]
        
        # Get all Pokemon of chosen rarity with their IDs
        pokemon_of_rarity = [(pokemon_id, pokemon_data) for pokemon_id, pokemon_data in self.pokemon_database.items() if pokemon_data['rarity'] == chosen_rarity]
        
        if not pokemon_of_rarity:
            # Fallback to any Pokemon
            pokemon_of_rarity = list(self.pokemon_database.items())
        
        if pokemon_of_rarity:
            pokemon_id, pokemon_data = random.choice(pokemon_of_rarity)
            # Add the ID to the pokemon data
            pokemon_with_id = pokemon_data.copy()
            pokemon_with_id['id'] = int(pokemon_id)
            return pokemon_with_id
        
        return None
    
    def load_player_data(self):
        """Load player data from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {}
        return {}
    
    def save_player_data(self):
        """Save player data to JSON file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.player_data, f, indent=2)
        except Exception as e:
            print(f"Error saving player data: {e}")
    
    def initialize_player(self, user_id):
        """Initialize a new player with starting inventory"""
        user_id = str(user_id)
        if user_id not in self.player_data:
            self.player_data[user_id] = {
                "pokemon": [],
                "pokeballs": {"normal": 5, "master": 0},
                "last_encounter": None,
                "stats": {
                    "total_caught": 0,
                    "total_encounters": 0,
                    "join_date": datetime.now().isoformat()
                }
            }
            self.save_player_data()
    
    def can_encounter(self, user_id):
        """Check if user can encounter a Pokemon (cooldown system)"""
        user_id = str(user_id)
        if user_id not in self.player_data:
            return True
        
        last_encounter = self.player_data[user_id].get("last_encounter")
        if not last_encounter:
            return True
        
        last_time = datetime.fromisoformat(last_encounter)
        cooldown = timedelta(minutes=5)  # 5 minute cooldown between encounters
        
        return datetime.now() - last_time >= cooldown
    
    def get_random_pokemon(self):
        """Get a random Pokemon based on rarity weights"""
        return self.get_random_pokemon_by_rarity()
    
    @commands.command(name='encounter', aliases=['wild', 'pokemon'])
    async def encounter_pokemon(self, ctx):
        """Encounter a wild Pokemon"""
        user_id = str(ctx.author.id)
        self.initialize_player(user_id)
        
        # Check cooldown
        if not self.can_encounter(user_id):
            last_encounter = datetime.fromisoformat(self.player_data[user_id]["last_encounter"])
            next_encounter = last_encounter + timedelta(minutes=5)
            time_left = next_encounter - datetime.now()
            minutes_left = int(time_left.total_seconds() / 60)
            
            embed = discord.Embed(
                title="⏱️ Cooldown Active",
                description=f"Please wait {minutes_left + 1} more minute(s) before your next encounter.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        # Get random Pokemon
        pokemon = self.get_random_pokemon()
        
        # Update player stats
        self.player_data[user_id]["last_encounter"] = datetime.now().isoformat()
        self.player_data[user_id]["stats"]["total_encounters"] += 1
        
        # Store current encounter for catching (store the full Pokemon data)
        self.player_data[user_id]["current_encounter"] = pokemon
        self.save_player_data()
        
        # Create encounter embed with Pokemon image
        embed = discord.Embed(
            title=f"🌿 Wild {pokemon['name']} Appeared!",
            description=f"**{ctx.author.mention}** encountered a wild **{pokemon['name']}**!\n\n*{pokemon['description']}*\n\n**This is your personal encounter - only you can catch it!**",
            color=self.get_type_color(pokemon['types'])
        )
        
        # Add Pokemon image
        embed.set_image(url=pokemon['image_url'])
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        
        # Format types
        type_text = " / ".join(pokemon['types'])
        embed.add_field(name="Type", value=f"{type_text}", inline=True)
        embed.add_field(name="Rarity", value=f"{pokemon['rarity']}", inline=True)
        embed.add_field(name="Catch Rate", value=f"{int(pokemon['catch_rate'] * 100)}%", inline=True)
        
        # Add ID and generation info
        embed.add_field(name="Pokedex #", value=f"#{pokemon['id']}", inline=True)
        embed.add_field(name="Generation", value=f"Gen {pokemon['generation']}", inline=True)
        embed.add_field(name="Total Stats", value=f"{pokemon['stats'].get('total', sum(pokemon['stats'].values()))}", inline=True)
        
        # Add stats preview - clean format
        stats = pokemon['stats']
        stats_text = f"**HP:** {stats['hp']} | **ATK:** {stats['attack']} | **DEF:** {stats['defense']}\n**SP.ATK:** {stats['sp_attack']} | **SP.DEF:** {stats['sp_defense']} | **SPD:** {stats['speed']}"
        embed.add_field(name="📊 Base Stats", value=stats_text, inline=False)
        
        # Simple capture instructions
        embed.add_field(name="🎯 How to Catch", value="Use `!catch normal` or `!catch master` to attempt capture!", inline=False)
        
        # Pokeball inventory - clean format
        normal_balls = self.player_data[user_id]["pokeballs"]["normal"]
        master_balls = self.player_data[user_id]["pokeballs"].get("master", 0)
        ball_text = f"**{normal_balls}** Normal Pokeballs\n**{master_balls}** Master Balls"
        embed.add_field(name="Pokeballs", value=ball_text, inline=True)
        
        # Encounter info - simplified
        encounter_count = self.player_data[user_id]['stats']['total_encounters']
        embed.add_field(name="Personal Encounter", value=f"Only you can catch this!\nTotal encounters: {encounter_count}", inline=True)
        
        # Clean footer
        embed.set_footer(text=f"Personal encounter for {ctx.author.display_name} • Gen {pokemon['generation']} • Use !catch to capture")
        embed.set_author(name="Legion Pokemon", icon_url="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/poke-ball.png")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='catch')
    async def catch_pokemon(self, ctx, ball_type: str = "normal"):
        """Attempt to catch the currently encountered Pokemon"""
        user_id = str(ctx.author.id)
        self.initialize_player(user_id)
        
        # Check if there's a current encounter
        current_encounter = self.player_data[user_id].get("current_encounter")
        if not current_encounter:
            embed = discord.Embed(
                title="❌ No Pokemon to Catch",
                description="You need to encounter a Pokemon first! Use `!encounter` to find a wild Pokemon.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Validate ball type
        valid_ball_types = ["normal", "master"]
        if ball_type.lower() not in valid_ball_types:
            embed = discord.Embed(
                title="❌ Invalid Ball Type",
                description=f"Valid ball types are: `normal`, `master`\nUsage: `!catch normal` or `!catch master`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        ball_type = ball_type.lower()
        
        # Check if player has the specified pokeball type
        if self.player_data[user_id]["pokeballs"].get(ball_type, 0) <= 0:
            ball_name = "Normal Pokeballs" if ball_type == "normal" else "Master Balls"
            embed = discord.Embed(
                title="❌ No Pokeballs",
                description=f"You don't have any {ball_name} left!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Use the specified pokeball
        self.player_data[user_id]["pokeballs"][ball_type] -= 1
        
        # Calculate catch success
        pokemon = current_encounter
        catch_roll = random.random()
        
        # Master Ball has 100% catch rate, normal ball uses Pokemon's catch rate
        if ball_type == "master":
            caught = True
            catch_rate_used = 1.0
        else:
            caught = catch_roll <= pokemon['catch_rate']
            catch_rate_used = pokemon['catch_rate']
        
        ball_emoji = "⚾" if ball_type == "normal" else "🌟"
        ball_name = "Normal Pokeball" if ball_type == "normal" else "Master Ball"
        
        if caught:
            # Add Pokemon to collection
            caught_pokemon = {
                "name": pokemon['name'],
                "types": pokemon['types'],
                "rarity": pokemon['rarity'],
                "caught_date": datetime.now().isoformat(),
                "id": len(self.player_data[user_id]["pokemon"]) + 1,
                "stats": pokemon['stats'],
                "generation": pokemon['generation'],
                "description": pokemon['description'],
                "image_url": pokemon['image_url'],
                "sprite_url": pokemon['sprite_url'],
                "caught_with": ball_type
            }
            
            self.player_data[user_id]["pokemon"].append(caught_pokemon)
            self.player_data[user_id]["stats"]["total_caught"] += 1
            
            embed = discord.Embed(
                title="🎉 Pokemon Caught!",
                description=f"**Congratulations {ctx.author.mention}!**\n\nYou successfully caught **{pokemon['name']}**!\nIt's now part of your collection.",
                color=self.get_type_color(pokemon['types'])
            )
            embed.set_image(url=pokemon['image_url'])
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            
            # Add Pokemon info
            embed.add_field(name="Type", value=f"{' / '.join(pokemon['types'])}", inline=True)
            embed.add_field(name="Rarity", value=f"{pokemon['rarity']}", inline=True)
            embed.add_field(name="Collection ID", value=f"#{caught_pokemon['id']}", inline=True)
            
            # Add capture details
            embed.add_field(name=f"{ball_emoji} Caught With", value=f"{ball_name}", inline=True)
            embed.add_field(name="Source", value="Personal Encounter", inline=True)
            embed.add_field(name="Generation", value=f"Gen {pokemon['generation']}", inline=True)
            
            # Simple collection info
            total_caught = len(self.player_data[user_id]["pokemon"])
            embed.add_field(name="🏆 Collection Progress", value=f"Total Pokemon: {total_caught}", inline=False)
            
            embed.set_footer(text=f"Caught by {ctx.author.display_name}")
            embed.set_author(name="Legion Pokemon", icon_url="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/poke-ball.png")
            
        else:
            embed = discord.Embed(
                title="💨 Pokemon Escaped!",
                description=f"**{pokemon['name']}** broke free from the {ball_name} and escaped!\n\nTry encountering another Pokemon with `!encounter`.",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=pokemon['sprite_url'])
            embed.add_field(name="Next Steps", value=f"• Use `!encounter` to find another Pokemon\n• Try using a Master Ball for guaranteed success\n• This Pokemon had a {int(pokemon['catch_rate'] * 100)}% catch rate", inline=False)
        
        # Add remaining pokeball count
        remaining_normal = self.player_data[user_id]["pokeballs"]["normal"]
        remaining_master = self.player_data[user_id]["pokeballs"].get("master", 0)
        ball_text = f"**{remaining_normal}** Normal Pokeballs"
        if remaining_master > 0:
            ball_text += f"\n**{remaining_master}** Master Balls"
        embed.add_field(name="Pokeballs Remaining", value=ball_text, inline=True)
        
        # Clear current encounter
        self.player_data[user_id]["current_encounter"] = None
        self.save_player_data()
        
        await ctx.send(embed=embed)
    
    @commands.command(name='pokemon_list', aliases=['pokedex', 'collection'])
    async def pokemon_collection(self, ctx, user: discord.Member = None):
        """View your Pokemon collection or another user's collection"""
        # If no user mentioned, show the author's collection
        if user is None:
            user = ctx.author
            user_id = str(ctx.author.id)
            is_own_collection = True
        else:
            user_id = str(user.id)
            is_own_collection = (user.id == ctx.author.id)
        
        self.initialize_player(user_id)
        
        pokemon_list = self.player_data[user_id]["pokemon"]
        
        if not pokemon_list:
            if is_own_collection:
                embed = discord.Embed(
                    title="📖 Your Collection",
                    description="You haven't caught any Pokemon yet!\nUse `!encounter` to find wild Pokemon.",
                    color=discord.Color.blue()
                )
            else:
                embed = discord.Embed(
                    title=f"📖 {user.display_name}'s Collection",
                    description=f"{user.display_name} hasn't caught any Pokemon yet!",
                    color=discord.Color.blue()
                )
            await ctx.send(embed=embed)
            return
        
        # Create collection embed
        if is_own_collection:
            embed = discord.Embed(
                title=f"📖 {ctx.author.display_name}'s Collection",
                description=f"**Total Pokemon:** {len(pokemon_list)}",
                color=discord.Color.blue()
            )
        else:
            embed = discord.Embed(
                title=f"📖 {user.display_name}'s Collection",
                description=f"**Total Pokemon:** {len(pokemon_list)}",
                color=discord.Color.blue()
            )
        
        # Group Pokemon by rarity
        by_rarity = {}
        for pokemon in pokemon_list:
            rarity = pokemon['rarity']
            if rarity not in by_rarity:
                by_rarity[rarity] = []
            by_rarity[rarity].append(pokemon)
        
        # Add Pokemon by rarity (simplified)
        rarity_emojis = {
            "Common": "⚪",
            "Uncommon": "🟢", 
            "Rare": "🔵",
            "Legendary": "🟡"
        }
        
        # Create simpler showcase for each rarity
        for rarity in ["Legendary", "Rare", "Uncommon", "Common"]:
            if rarity in by_rarity:
                pokemon_names = []
                for p in by_rarity[rarity]:
                    type_text = " / ".join(p.get('types', [p.get('type', 'Unknown')]))
                    pokemon_names.append(f"**#{p['id']} {p['name']}** ({type_text})")
                
                display_names = pokemon_names[:6]  # Show fewer Pokemon for cleaner display
                if len(pokemon_names) > 6:
                    display_names.append(f"*... and {len(pokemon_names) - 6} more*")
                
                embed.add_field(
                    name=f"{rarity_emojis.get(rarity, '⚪')} {rarity} ({len(by_rarity[rarity])})",
                    value="\n".join(display_names),
                    inline=False
                )
        
        # Simple collection stats
        wild_caught = len([p for p in pokemon_list if p.get('caught_from') == 'wild_spawn'])
        encounter_caught = len([p for p in pokemon_list if p.get('caught_from') != 'wild_spawn'])
        
        # Generation breakdown
        gen_count = {}
        for p in pokemon_list:
            gen = p.get('generation', 'Unknown')
            gen_count[gen] = gen_count.get(gen, 0) + 1
        
        stats_text = f"**Wild Catches:** {wild_caught} | **Encounters:** {encounter_caught}"
        if gen_count:
            gen_display = " | ".join([f"Gen {gen}: {count}" for gen, count in sorted(gen_count.items()) if isinstance(gen, int)][:3])
            if gen_display:
                stats_text += f"\n{gen_display}"
        
        embed.add_field(
            name="📊 Collection Stats", 
            value=stats_text,
            inline=False
        )
        
        # Add simple image display
        if pokemon_list:
            # Find the most recent Pokemon
            display_pokemon = max(pokemon_list, key=lambda x: x.get('caught_date', ''))
            
            # Set the image
            if display_pokemon and 'image_url' in display_pokemon:
                embed.set_image(url=display_pokemon['image_url'])
                
            # Simple footer
            embed.set_footer(text=f"Showing {display_pokemon['name']} • {ctx.author.display_name}")
        else:
            embed.set_footer(text=f"Collection for {user.display_name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='pokemon_stats', aliases=['stats'])
    async def pokemon_stats(self, ctx):
        """View your Pokemon game statistics"""
        user_id = str(ctx.author.id)
        self.initialize_player(user_id)
        
        stats = self.player_data[user_id]["stats"]
        pokemon_count = len(self.player_data[user_id]["pokemon"])
        pokeballs = self.player_data[user_id]["pokeballs"]["normal"]
        
        embed = discord.Embed(
            title=f"📊 {ctx.author.display_name}'s Pokemon Stats",
            color=discord.Color.purple()
        )
        
        embed.add_field(name="🏆 Pokemon Caught", value=str(pokemon_count), inline=True)
        embed.add_field(name="👁️ Total Encounters", value=str(stats["total_encounters"]), inline=True)
        embed.add_field(name="⚾ Pokeballs Left", value=str(pokeballs), inline=True)
        
        if stats["total_encounters"] > 0:
            catch_rate = (stats["total_caught"] / stats["total_encounters"]) * 100
            embed.add_field(name="🎯 Catch Rate", value=f"{catch_rate:.1f}%", inline=True)
        
        join_date = datetime.fromisoformat(stats["join_date"]).strftime("%B %d, %Y")
        embed.add_field(name="📅 Trainer Since", value=join_date, inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='inventory', aliases=['inv', 'bag'])
    async def pokemon_inventory(self, ctx):
        """View your Pokemon inventory and items"""
        user_id = str(ctx.author.id)
        self.initialize_player(user_id)
        
        # Get player data
        player_data = self.player_data[user_id]
        pokeballs = player_data["pokeballs"]
        stats = player_data["stats"]
        pokemon_count = len(player_data["pokemon"])
        
        # Create inventory embed
        embed = discord.Embed(
            title=f"🎒 {ctx.author.display_name}'s Inventory",
            description="Your Pokemon trainer inventory and items",
            color=discord.Color.green()
        )
        
        # Add user avatar
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        
        # Pokeballs section
        normal_balls = pokeballs.get("normal", 0)
        master_balls = pokeballs.get("master", 0)
        
        pokeball_text = f"⚾ **Normal Pokeballs:** {normal_balls}\n🌟 **Master Balls:** {master_balls}"
        total_balls = normal_balls + master_balls
        pokeball_text += f"\n📊 **Total Pokeballs:** {total_balls}"
        
        embed.add_field(
            name="⚾ Pokeballs", 
            value=pokeball_text, 
            inline=True
        )
        
        # Pokemon collection summary
        if pokemon_count > 0:
            # Get rarity breakdown
            rarity_counts = {"Common": 0, "Uncommon": 0, "Rare": 0, "Legendary": 0}
            for pokemon in player_data["pokemon"]:
                rarity = pokemon.get('rarity', 'Common')
                if rarity in rarity_counts:
                    rarity_counts[rarity] += 1
            
            collection_text = f"🏆 **Total Pokemon:** {pokemon_count}\n"
            collection_text += f"🟡 **Legendary:** {rarity_counts['Legendary']}\n"
            collection_text += f"🔵 **Rare:** {rarity_counts['Rare']}\n"
            collection_text += f"🟢 **Uncommon:** {rarity_counts['Uncommon']}\n"
            collection_text += f"⚪ **Common:** {rarity_counts['Common']}"
        else:
            collection_text = "🏆 **Total Pokemon:** 0\nNo Pokemon caught yet!"
        
        embed.add_field(
            name="📖 Pokemon Collection", 
            value=collection_text, 
            inline=True
        )
        
        # Trainer stats
        total_encounters = stats.get("total_encounters", 0)
        total_caught = stats.get("total_caught", 0)
        catch_rate = (total_caught / total_encounters * 100) if total_encounters > 0 else 0
        
        stats_text = f"👁️ **Encounters:** {total_encounters}\n"
        stats_text += f"🎯 **Catch Rate:** {catch_rate:.1f}%\n"
        
        # Join date
        join_date = datetime.fromisoformat(stats["join_date"]).strftime("%B %d, %Y")
        stats_text += f"📅 **Trainer Since:** {join_date}"
        
        embed.add_field(
            name="📊 Trainer Stats", 
            value=stats_text, 
            inline=False
        )
        
        # Add tips section
        tips_text = "💡 Use `!encounter` to find wild Pokemon\n"
        tips_text += "💡 Use `!catch normal` or `!catch master` to catch Pokemon\n"
        tips_text += "💡 Use `!collection` to view your Pokemon"
        
        embed.add_field(
            name="💡 Quick Tips", 
            value=tips_text, 
            inline=False
        )
        
        # Footer with current encounter status
        current_encounter = player_data.get("current_encounter")
        if current_encounter:
            footer_text = f"🌿 Active Encounter: {current_encounter['name']} | Ready to catch!"
        else:
            # Check cooldown
            if self.can_encounter(user_id):
                footer_text = "✅ Ready for next encounter!"
            else:
                last_encounter = datetime.fromisoformat(player_data["last_encounter"])
                next_encounter = last_encounter + timedelta(minutes=5)
                time_left = next_encounter - datetime.now()
                minutes_left = int(time_left.total_seconds() / 60) + 1
                footer_text = f"⏰ Next encounter in {minutes_left} minute(s)"
        
        embed.set_footer(text=footer_text)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='pokemon_info', aliases=['pinfo', 'pokemon_detail'])
    async def pokemon_info(self, ctx, *, pokemon_identifier):
        """View detailed information about a specific Pokemon in your collection"""
        user_id = str(ctx.author.id)
        self.initialize_player(user_id)
        
        pokemon_list = self.player_data[user_id]["pokemon"]
        
        if not pokemon_list:
            embed = discord.Embed(
                title="❌ No Pokemon Found",
                description="You haven't caught any Pokemon yet! Use `!encounter` to find wild Pokemon.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Try to find Pokemon by ID or name
        found_pokemon = None
        
        # Check if identifier is a number (Pokemon ID)
        if pokemon_identifier.startswith('#'):
            pokemon_identifier = pokemon_identifier[1:]
        
        if pokemon_identifier.isdigit():
            pokemon_id = int(pokemon_identifier)
            found_pokemon = next((p for p in pokemon_list if p['id'] == pokemon_id), None)
        else:
            # Search by name
            found_pokemon = next((p for p in pokemon_list if p['name'].lower() == pokemon_identifier.lower()), None)
        
        if not found_pokemon:
            embed = discord.Embed(
                title="❌ Pokemon Not Found",
                description=f"Could not find Pokemon '{pokemon_identifier}' in your collection.\nUse `!collection` to see all your Pokemon.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Create detailed Pokemon info embed
        embed = discord.Embed(
            title=f"📋 {found_pokemon['name']} - Details",
            description=found_pokemon.get('description', 'No description available.'),
            color=self.get_type_color(found_pokemon.get('types', ['Normal']))
        )
        
        # Add Pokemon image
        if 'image_url' in found_pokemon:
            embed.set_image(url=found_pokemon['image_url'])
        if 'sprite_url' in found_pokemon:
            embed.set_thumbnail(url=found_pokemon['sprite_url'])
        
        # Basic info
        types = found_pokemon.get('types', [found_pokemon.get('type', 'Unknown')])
        if isinstance(types, str):
            types = [types]
        
        embed.add_field(name="🆔 Collection ID", value=f"#{found_pokemon['id']}", inline=True)
        embed.add_field(name="🏷️ Type", value=" / ".join(types), inline=True)
        embed.add_field(name="⭐ Rarity", value=found_pokemon['rarity'], inline=True)
        
        # Caught date
        caught_date = datetime.fromisoformat(found_pokemon['caught_date']).strftime("%B %d, %Y at %I:%M %p")
        embed.add_field(name="📅 Caught On", value=caught_date, inline=True)
        
        # Generation info
        generation = found_pokemon.get('generation', 'Unknown')
        embed.add_field(name="🌍 Generation", value=f"Gen {generation}", inline=True)
        embed.add_field(name="📊 Base Stat Total", value=found_pokemon.get('stats', {}).get('total', 'Unknown'), inline=True)
        
        # Detailed stats
        if 'stats' in found_pokemon:
            stats = found_pokemon['stats']
            stats_text = (
                f"**HP:** {stats.get('hp', 0)} | **Attack:** {stats.get('attack', 0)} | **Defense:** {stats.get('defense', 0)}\n"
                f"**Sp. Attack:** {stats.get('sp_attack', 0)} | **Sp. Defense:** {stats.get('sp_defense', 0)} | **Speed:** {stats.get('speed', 0)}"
            )
            embed.add_field(name="📊 Base Stats", value=stats_text, inline=False)
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
    
    # Admin Commands
    @commands.command(name='pokemon_admin', aliases=['padmin'])
    async def pokemon_admin(self, ctx):
        """Admin command to view Pokemon database statistics"""
        if not Config.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use admin commands.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Get database statistics
        total_pokemon = len(self.pokemon_database)
        
        # Count by generation
        generation_counts = {}
        rarity_counts = {"Common": 0, "Uncommon": 0, "Rare": 0, "Legendary": 0}
        
        for pokemon in self.pokemon_database.values():
            gen = pokemon['generation']
            rarity = pokemon['rarity']
            
            if gen not in generation_counts:
                generation_counts[gen] = 0
            generation_counts[gen] += 1
            rarity_counts[rarity] += 1
        
        embed = discord.Embed(
            title="🔧 Pokemon Database Admin Panel",
            description=f"Database Statistics and Management",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📊 Total Pokemon", 
            value=f"**{total_pokemon}** Pokemon in database\n*Target: 1025+ Pokemon*", 
            inline=False
        )
        
        # Generation breakdown
        gen_text = ""
        for gen in sorted(generation_counts.keys()):
            count = generation_counts[gen]
            gen_text += f"**Generation {gen}:** {count} Pokemon\n"
        
        embed.add_field(name="🌍 By Generation", value=gen_text, inline=True)
        
        # Rarity breakdown
        rarity_text = ""
        for rarity, count in rarity_counts.items():
            percentage = (count / total_pokemon * 100) if total_pokemon > 0 else 0
            rarity_text += f"**{rarity}:** {count} ({percentage:.1f}%)\n"
        
        embed.add_field(name="⭐ By Rarity", value=rarity_text, inline=True)
        
        # Player statistics
        total_players = len(self.player_data)
        total_caught = sum(len(player.get('pokemon', [])) for player in self.player_data.values())
        
        embed.add_field(
            name="👥 Player Stats",
            value=f"**Active Players:** {total_players}\n**Total Pokemon Caught:** {total_caught}",
            inline=True
        )
        
        # Database status
        missing_gens = []
        max_gen = max(generation_counts.keys()) if generation_counts else 0
        for gen in range(1, 10):  # Generations 1-9
            if gen not in generation_counts:
                missing_gens.append(str(gen))
        
        status_text = f"**Current:** Gen 1-{max_gen}\n"
        if missing_gens:
            status_text += f"**Missing:** Gen {', '.join(missing_gens[:5])}"
            if len(missing_gens) > 5:
                status_text += f" +{len(missing_gens)-5} more"
        else:
            status_text += "**Status:** Complete (1-9)"
        
        embed.add_field(name="🎯 Database Status", value=status_text, inline=False)
        
        embed.set_footer(text=f"Admin: {ctx.author.display_name} | Complete Pokemon Database - All 1025 Pokemon Available")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='give_pokeball', aliases=['give_ball', 'pokeball_admin'])
    async def give_pokeball(self, ctx, user: discord.Member, ball_type: str, count: int):
        """Admin command to give pokeballs to a user"""
        if not Config.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use admin commands.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Validate ball type
        valid_ball_types = ["normal", "master"]
        if ball_type.lower() not in valid_ball_types:
            embed = discord.Embed(
                title="❌ Invalid Ball Type",
                description=f"Valid ball types are: {', '.join(valid_ball_types)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Validate count
        if count <= 0:
            embed = discord.Embed(
                title="❌ Invalid Count",
                description="Count must be a positive number.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Initialize player if needed
        user_id = str(user.id)
        self.initialize_player(user_id)
        
        # Ensure the ball type exists in the player's data
        if ball_type.lower() not in self.player_data[user_id]["pokeballs"]:
            self.player_data[user_id]["pokeballs"][ball_type.lower()] = 0
        
        # Add pokeballs
        self.player_data[user_id]["pokeballs"][ball_type.lower()] += count
        self.save_player_data()
        
        # Create confirmation embed
        ball_emoji = "⚾" if ball_type.lower() == "normal" else "🌟"
        embed = discord.Embed(
            title="✅ Pokeballs Given",
            description=f"Successfully gave {count} {ball_type.title()} Pokeball(s) to {user.mention}!",
            color=discord.Color.green()
        )
        
        # Show user's current pokeball count
        current_normal = self.player_data[user_id]["pokeballs"].get("normal", 0)
        current_master = self.player_data[user_id]["pokeballs"].get("master", 0)
        
        embed.add_field(
            name=f"{ball_emoji} {user.display_name}'s Pokeballs",
            value=f"**Normal:** {current_normal}\n**Master:** {current_master}",
            inline=True
        )
        
        embed.add_field(
            name="📋 Action Details",
            value=f"**Given:** {count} {ball_type.title()} Pokeball(s)\n**To:** {user.display_name}\n**By:** {ctx.author.display_name}",
            inline=True
        )
        
        embed.set_footer(text=f"Admin Action | Executed by {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='wild_catch', aliases=['wcatch'])
    async def wild_catch(self, ctx):
        """Attempt to catch the current wild Pokemon in the pokemon channel"""
        # Check if this is the pokemon channel
        if ctx.channel.name != self.wild_spawn_data["spawn_channel"]:
            embed = discord.Embed(
                title="❌ Wrong Channel",
                description=f"Wild Pokemon can only be caught in the #{self.wild_spawn_data['spawn_channel']} channel!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        user_id = str(ctx.author.id)
        self.initialize_player(user_id)
        
        # Check if there's a current wild Pokemon
        current_wild = self.wild_spawn_data.get("current_wild")
        if not current_wild or current_wild.get("caught_by"):
            embed = discord.Embed(
                title="❌ No Wild Pokemon",
                description="There's no wild Pokemon available to catch right now!\nWait for the next wild spawn (every 30 minutes).",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Check if player has pokeballs
        if self.player_data[user_id]["pokeballs"]["normal"] <= 0:
            embed = discord.Embed(
                title="❌ No Pokeballs",
                description="You don't have any Normal Pokeballs left! Wild Pokemon can only be caught with Normal Pokeballs.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Use a pokeball
        self.player_data[user_id]["pokeballs"]["normal"] -= 1
        
        # Calculate catch success
        pokemon = current_wild["pokemon"]
        catch_roll = random.random()
        caught = catch_roll <= pokemon['catch_rate']
        
        if caught:
            # Mark as caught by this user
            self.wild_spawn_data["current_wild"]["caught_by"] = {
                "user_id": user_id,
                "username": ctx.author.display_name,
                "caught_time": datetime.now().isoformat()
            }
            self.save_wild_spawn_data()
            
            # Add Pokemon to collection
            caught_pokemon = {
                "name": pokemon['name'],
                "types": pokemon['types'],
                "rarity": pokemon['rarity'],
                "caught_date": datetime.now().isoformat(),
                "id": len(self.player_data[user_id]["pokemon"]) + 1,
                "stats": pokemon['stats'],
                "generation": pokemon['generation'],
                "description": pokemon['description'],
                "image_url": pokemon['image_url'],
                "sprite_url": pokemon['sprite_url'],
                "caught_with": "normal",
                "caught_from": "wild_spawn"
            }
            
            self.player_data[user_id]["pokemon"].append(caught_pokemon)
            self.player_data[user_id]["stats"]["total_caught"] += 1
            self.save_player_data()
            
            embed = discord.Embed(
                title="🎉 Pokemon Caught!",
                description=f"**Congratulations {ctx.author.mention}!**\n\nYou successfully caught the wild **{pokemon['name']}**!\nIt's now part of your collection.",
                color=self.get_type_color(pokemon['types'])
            )
            embed.set_image(url=pokemon['image_url'])
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            
            # Add Pokemon info
            embed.add_field(name="Type", value=" / ".join(pokemon['types']), inline=True)
            embed.add_field(name="Rarity", value=f"{pokemon['rarity']}", inline=True)
            embed.add_field(name="Collection ID", value=f"#{caught_pokemon['id']}", inline=True)
            
            # Simple achievement text
            total_caught = len(self.player_data[user_id]["pokemon"])
            embed.add_field(name="🏆 Victory!", value=f"You caught the wild {pokemon['name']}!\nTotal Pokemon: {total_caught}", inline=False)
            
            embed.set_footer(text=f"Caught by {ctx.author.display_name}")
            
        else:
            embed = discord.Embed(
                title="💨 Pokemon Escaped!",
                description=f"The wild **{pokemon['name']}** broke free! Other trainers can still try to catch it.",
                color=discord.Color.orange()
            )
            embed.set_thumbnail(url=pokemon['sprite_url'])
            embed.add_field(name="Still Available", value="The Pokemon is still available for others to catch!", inline=False)
        
        # Add remaining pokeball count
        remaining_balls = self.player_data[user_id]["pokeballs"]["normal"]
        embed.add_field(name="Pokeballs Remaining", value=f"{remaining_balls} Normal Pokeballs", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='wild_status', aliases=['wstatus'])
    async def wild_status(self, ctx):
        """Check the status of wild Pokemon spawning"""
        current_wild = self.wild_spawn_data.get("current_wild")
        
        embed = discord.Embed(
            title="🌲 Wild Pokemon Status",
            color=discord.Color.blue()
        )
        
        if current_wild and not current_wild.get("caught_by"):
            pokemon = current_wild["pokemon"]
            spawn_time = datetime.fromisoformat(current_wild["spawn_time"])
            time_available = datetime.now() - spawn_time
            
            embed.description = f"A wild **{pokemon['name']}** is currently available!"
            embed.add_field(name="🏷️ Type", value=" / ".join(pokemon['types']), inline=True)
            embed.add_field(name="⭐ Rarity", value=pokemon['rarity'], inline=True)
            embed.add_field(name="⏰ Available for", value=f"{int(time_available.total_seconds() / 60)} minutes", inline=True)
            embed.add_field(name="📍 Location", value=f"#{self.wild_spawn_data['spawn_channel']} channel", inline=True)
            embed.add_field(name="🎯 How to Catch", value="Use `!wild_catch` in the pokemon channel!", inline=True)
            embed.set_thumbnail(url=pokemon['sprite_url'])
        elif current_wild and current_wild.get("caught_by"):
            caught_info = current_wild["caught_by"]
            pokemon = current_wild["pokemon"]
            
            embed.description = f"The wild **{pokemon['name']}** was already caught!"
            embed.add_field(name="🏆 Caught by", value=caught_info["username"], inline=True)
            embed.add_field(name="⏰ Caught", value="Recently", inline=True)
            embed.add_field(name="🔄 Next Spawn", value="Wait for next 30-minute cycle", inline=True)
        else:
            embed.description = "No wild Pokemon is currently available."
            embed.add_field(name="⏰ Next Spawn", value="Check back later - spawns every 30 minutes!", inline=True)
            embed.add_field(name="📍 Spawn Location", value=f"#{self.wild_spawn_data['spawn_channel']} channel", inline=True)
        
        # Show last spawn time
        if self.wild_spawn_data.get("last_spawn"):
            last_spawn = datetime.fromisoformat(self.wild_spawn_data["last_spawn"])
            time_since = datetime.now() - last_spawn
            embed.add_field(name="🕐 Last Spawn", value=f"{int(time_since.total_seconds() / 60)} minutes ago", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='force_wild_spawn', aliases=['fws'])
    async def force_wild_spawn(self, ctx):
        """Admin command to manually trigger a wild Pokemon spawn"""
        if not Config.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use admin commands.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        await self.spawn_wild_pokemon()
        
        embed = discord.Embed(
            title="✅ Wild Spawn Triggered",
            description=f"A wild Pokemon has been manually spawned in #{self.wild_spawn_data['spawn_channel']}!",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Triggered by {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='debug_channels', aliases=['dchannels'])
    async def debug_channels(self, ctx):
        """Debug command to check available channels and bot permissions"""
        if not Config.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use admin commands.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🔧 Channel Debug Information",
            description="Bot channel access and permissions debug",
            color=discord.Color.blue()
        )
        
        target_channel = self.wild_spawn_data["spawn_channel"]
        embed.add_field(
            name="🎯 Target Channel",
            value=f"Looking for: `{target_channel}`",
            inline=False
        )
        
        # Check each guild
        for guild in self.bot.guilds:
            guild_info = f"**Guild:** {guild.name} (ID: {guild.id})\n"
            
            # List all text channels
            text_channels = [ch.name for ch in guild.text_channels]
            guild_info += f"**Text Channels:** {', '.join(text_channels[:10])}"
            if len(text_channels) > 10:
                guild_info += f" ... (+{len(text_channels)-10} more)"
            
            # Check if target channel exists
            target_ch = discord.utils.get(guild.text_channels, name=target_channel)
            if target_ch:
                guild_info += f"\n✅ **Found `{target_channel}` channel!**"
                guild_info += f"\n📍 **Channel ID:** {target_ch.id}"
                
                # Check permissions
                perms = target_ch.permissions_for(guild.me)
                guild_info += f"\n🔑 **Permissions:** "
                guild_info += f"View: {'✅' if perms.view_channel else '❌'} | "
                guild_info += f"Send: {'✅' if perms.send_messages else '❌'} | "
                guild_info += f"Embed: {'✅' if perms.embed_links else '❌'}"
            else:
                guild_info += f"\n❌ **`{target_channel}` channel not found**"
                
                # Check for similar names
                similar = [ch.name for ch in guild.text_channels if target_channel.lower() in ch.name.lower()]
                if similar:
                    guild_info += f"\n🔍 **Similar channels:** {', '.join(similar[:3])}"
            
            embed.add_field(
                name=f"🏠 {guild.name}",
                value=guild_info,
                inline=False
            )
        
        embed.set_footer(text=f"Debug requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(Pokemon(bot))