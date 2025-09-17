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

class Pokemon(commands.Cog):
    """Cog for Pokemon game functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "pokemon_data.json"
        self.player_data = self.load_player_data()
        
        # Pokemon database - basic starter Pokemon for now
        self.pokemon_database = {
            "common": [
                {"name": "Pidgey", "type": "Normal/Flying", "rarity": "Common", "catch_rate": 0.8},
                {"name": "Rattata", "type": "Normal", "rarity": "Common", "catch_rate": 0.8},
                {"name": "Caterpie", "type": "Bug", "rarity": "Common", "catch_rate": 0.9},
                {"name": "Weedle", "type": "Bug/Poison", "rarity": "Common", "catch_rate": 0.9},
                {"name": "Magikarp", "type": "Water", "rarity": "Common", "catch_rate": 0.9}
            ],
            "uncommon": [
                {"name": "Pikachu", "type": "Electric", "rarity": "Uncommon", "catch_rate": 0.6},
                {"name": "Bulbasaur", "type": "Grass/Poison", "rarity": "Uncommon", "catch_rate": 0.5},
                {"name": "Charmander", "type": "Fire", "rarity": "Uncommon", "catch_rate": 0.5},
                {"name": "Squirtle", "type": "Water", "rarity": "Uncommon", "catch_rate": 0.5},
                {"name": "Eevee", "type": "Normal", "rarity": "Uncommon", "catch_rate": 0.4}
            ],
            "rare": [
                {"name": "Dratini", "type": "Dragon", "rarity": "Rare", "catch_rate": 0.3},
                {"name": "Lapras", "type": "Water/Ice", "rarity": "Rare", "catch_rate": 0.2},
                {"name": "Snorlax", "type": "Normal", "rarity": "Rare", "catch_rate": 0.25}
            ],
            "legendary": [
                {"name": "Articuno", "type": "Ice/Flying", "rarity": "Legendary", "catch_rate": 0.1},
                {"name": "Zapdos", "type": "Electric/Flying", "rarity": "Legendary", "catch_rate": 0.1},
                {"name": "Moltres", "type": "Fire/Flying", "rarity": "Legendary", "catch_rate": 0.1}
            ]
        }
    
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
        # Rarity weights: Common 60%, Uncommon 25%, Rare 10%, Legendary 5%
        rarity_weights = {
            "common": 0.60,
            "uncommon": 0.25,
            "rare": 0.10,
            "legendary": 0.05
        }
        
        rand = random.random()
        cumulative = 0
        
        for rarity, weight in rarity_weights.items():
            cumulative += weight
            if rand <= cumulative:
                return random.choice(self.pokemon_database[rarity])
        
        # Fallback to common
        return random.choice(self.pokemon_database["common"])
    
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
        
        # Store current encounter for catching
        self.player_data[user_id]["current_encounter"] = pokemon
        self.save_player_data()
        
        # Create encounter embed
        rarity_colors = {
            "Common": discord.Color.light_grey(),
            "Uncommon": discord.Color.green(),
            "Rare": discord.Color.blue(),
            "Legendary": discord.Color.gold()
        }
        
        embed = discord.Embed(
            title=f"🌿 Wild Pokemon Encountered!",
            description=f"A wild **{pokemon['name']}** appeared!",
            color=rarity_colors.get(pokemon['rarity'], discord.Color.blue())
        )
        embed.add_field(name="Type", value=pokemon['type'], inline=True)
        embed.add_field(name="Rarity", value=pokemon['rarity'], inline=True)
        embed.add_field(name="🎯 Actions", value="Use `!catch` to attempt to catch this Pokemon!", inline=False)
        
        # Add pokeball count
        pokeballs = self.player_data[user_id]["pokeballs"]["normal"]
        embed.add_field(name="⚾ Your Pokeballs", value=f"{pokeballs} Normal Pokeballs", inline=True)
        
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
                "type": pokemon['type'],
                "rarity": pokemon['rarity'],
                "caught_date": datetime.now().isoformat(),
                "id": len(self.player_data[user_id]["pokemon"]) + 1
            }
            
            self.player_data[user_id]["pokemon"].append(caught_pokemon)
            self.player_data[user_id]["stats"]["total_caught"] += 1
            
            embed = discord.Embed(
                title="🎉 Pokemon Caught!",
                description=f"Congratulations! You successfully caught **{pokemon['name']}**!",
                color=discord.Color.green()
            )
            embed.add_field(name="Type", value=pokemon['type'], inline=True)
            embed.add_field(name="Rarity", value=pokemon['rarity'], inline=True)
            embed.add_field(name="Pokemon ID", value=f"#{caught_pokemon['id']}", inline=True)
        else:
            embed = discord.Embed(
                title="💨 Pokemon Escaped!",
                description=f"Oh no! **{pokemon['name']}** broke free and escaped!",
                color=discord.Color.red()
            )
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
                pokemon_names = [f"#{p['id']} {p['name']}" for p in by_rarity[rarity]]
                embed.add_field(
                    name=f"{rarity_emojis.get(rarity, '⚪')} {rarity} ({len(by_rarity[rarity])})",
                    value="\n".join(pokemon_names) if len(pokemon_names) <= 10 else "\n".join(pokemon_names[:10]) + f"\n... and {len(pokemon_names) - 10} more",
                    inline=True
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

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(Pokemon(bot))