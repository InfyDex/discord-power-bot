"""
Pokemon Game cog for the Legion Discord Bot
Handles Pokemon encounters, catching, and collection management.
"""

import discord
from discord.ext import commands
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
        
        # Get all Pokemon of chosen rarity
        pokemon_of_rarity = [p for p in self.pokemon_database.values() if p['rarity'] == chosen_rarity]
        
        if not pokemon_of_rarity:
            # Fallback to any Pokemon
            pokemon_of_rarity = list(self.pokemon_database.values())
        
        return random.choice(pokemon_of_rarity) if pokemon_of_rarity else None
    
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
                "pokeballs": {"normal": 5},
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
                title="🕐 Encounter Cooldown",
                description=f"You need to wait {minutes_left + 1} more minute(s) before your next encounter!",
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
            title=f"🌿 Wild Pokemon Encountered!",
            description=f"A wild **{pokemon['name']}** appeared!\n\n*{pokemon['description']}*",
            color=self.get_type_color(pokemon['types'])
        )
        
        # Add Pokemon image
        embed.set_image(url=pokemon['image_url'])
        embed.set_thumbnail(url=pokemon['sprite_url'])
        
        # Format types
        type_text = " / ".join(pokemon['types'])
        embed.add_field(name="🏷️ Type", value=type_text, inline=True)
        embed.add_field(name="⭐ Rarity", value=pokemon['rarity'], inline=True)
        embed.add_field(name="🎲 Catch Rate", value=f"{int(pokemon['catch_rate'] * 100)}%", inline=True)
        
        # Add stats preview
        stats = pokemon['stats']
        stats_text = f"**HP:** {stats['hp']} | **ATK:** {stats['attack']} | **DEF:** {stats['defense']}\n**SP.ATK:** {stats['sp_attack']} | **SP.DEF:** {stats['sp_defense']} | **SPD:** {stats['speed']}"
        embed.add_field(name="📊 Base Stats", value=stats_text, inline=False)
        
        embed.add_field(name="🎯 Actions", value="Use `!catch` to attempt to catch this Pokemon!", inline=False)
        
        # Add pokeball count
        pokeballs = self.player_data[user_id]["pokeballs"]["normal"]
        embed.add_field(name="⚾ Your Pokeballs", value=f"{pokeballs} Normal Pokeballs", inline=True)
        
        # Add generation info
        embed.set_footer(text=f"Generation {pokemon['generation']} Pokemon | Pokedex Entry")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='catch')
    async def catch_pokemon(self, ctx):
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
        
        # Check if player has pokeballs
        if self.player_data[user_id]["pokeballs"]["normal"] <= 0:
            embed = discord.Embed(
                title="❌ No Pokeballs",
                description="You don't have any Pokeballs left! You'll need to get more to catch Pokemon.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Use a pokeball
        self.player_data[user_id]["pokeballs"]["normal"] -= 1
        
        # Calculate catch success
        pokemon = current_encounter
        catch_roll = random.random()
        caught = catch_roll <= pokemon['catch_rate']
        
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
                "sprite_url": pokemon['sprite_url']
            }
            
            self.player_data[user_id]["pokemon"].append(caught_pokemon)
            self.player_data[user_id]["stats"]["total_caught"] += 1
            
            embed = discord.Embed(
                title="🎉 Pokemon Caught!",
                description=f"Congratulations! You successfully caught **{pokemon['name']}**!",
                color=self.get_type_color(pokemon['types'])
            )
            embed.set_thumbnail(url=pokemon['sprite_url'])
            embed.add_field(name="🏷️ Type", value=" / ".join(pokemon['types']), inline=True)
            embed.add_field(name="⭐ Rarity", value=pokemon['rarity'], inline=True)
            embed.add_field(name="🆔 Pokemon ID", value=f"#{caught_pokemon['id']}", inline=True)
        else:
            embed = discord.Embed(
                title="💨 Pokemon Escaped!",
                description=f"Oh no! **{pokemon['name']}** broke free and escaped!",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=pokemon['sprite_url'])
            embed.add_field(name="Better luck next time!", value="Try encountering another Pokemon!", inline=False)
        
        # Add remaining pokeball count
        remaining_balls = self.player_data[user_id]["pokeballs"]["normal"]
        embed.add_field(name="⚾ Pokeballs Remaining", value=f"{remaining_balls} Normal Pokeballs", inline=True)
        
        # Clear current encounter
        self.player_data[user_id]["current_encounter"] = None
        self.save_player_data()
        
        await ctx.send(embed=embed)
    
    @commands.command(name='pokemon_list', aliases=['pokedex', 'collection'])
    async def pokemon_collection(self, ctx):
        """View your Pokemon collection"""
        user_id = str(ctx.author.id)
        self.initialize_player(user_id)
        
        pokemon_list = self.player_data[user_id]["pokemon"]
        
        if not pokemon_list:
            embed = discord.Embed(
                title="📖 Your Pokemon Collection",
                description="You haven't caught any Pokemon yet! Use `!encounter` to find wild Pokemon.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        # Create collection embed
        embed = discord.Embed(
            title=f"📖 {ctx.author.display_name}'s Pokemon Collection",
            description=f"You have caught {len(pokemon_list)} Pokemon!",
            color=discord.Color.blue()
        )
        
        # Group Pokemon by rarity
        by_rarity = {}
        for pokemon in pokemon_list:
            rarity = pokemon['rarity']
            if rarity not in by_rarity:
                by_rarity[rarity] = []
            by_rarity[rarity].append(pokemon)
        
        # Add fields for each rarity
        rarity_emojis = {
            "Common": "⚪",
            "Uncommon": "🟢", 
            "Rare": "🔵",
            "Legendary": "🟡"
        }
        
        for rarity in ["Legendary", "Rare", "Uncommon", "Common"]:
            if rarity in by_rarity:
                pokemon_names = []
                for p in by_rarity[rarity]:
                    type_text = " / ".join(p.get('types', [p.get('type', 'Unknown')]))
                    pokemon_names.append(f"#{p['id']} {p['name']} ({type_text})")
                
                display_names = pokemon_names[:8]  # Show max 8 per rarity
                if len(pokemon_names) > 8:
                    display_names.append(f"... and {len(pokemon_names) - 8} more")
                
                embed.add_field(
                    name=f"{rarity_emojis.get(rarity, '⚪')} {rarity} ({len(by_rarity[rarity])})",
                    value="\n".join(display_names),
                    inline=True
                )
        
        # Add collection stats
        total_stats = sum(p.get('stats', {}).get('total', 0) for p in pokemon_list)
        avg_stats = total_stats // len(pokemon_list) if pokemon_list else 0
        embed.add_field(
            name="📊 Collection Stats", 
            value=f"**Total Base Stats:** {total_stats}\n**Average Base Stats:** {avg_stats}",
            inline=False
        )
        
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
        
        embed.set_footer(text=f"Admin: {ctx.author.display_name} | Use !expand_pokemon to add more Pokemon")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='expand_pokemon')
    async def expand_pokemon_database(self, ctx):
        """Admin command to expand the Pokemon database"""
        if not Config.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use admin commands.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🚧 Database Expansion",
            description="To expand the Pokemon database to all 1025+ Pokemon:\n\n" +
                       "1. Run the database generator script\n" +
                       "2. The bot will automatically load new Pokemon\n" +
                       "3. Use `!pokemon_admin` to check updated stats\n\n" +
                       "*This feature requires manual database expansion.*",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="📝 Current Status",
            value=f"Database has {len(self.pokemon_database)} Pokemon\nTarget: 1025+ Pokemon from all generations",
            inline=False
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(Pokemon(bot))