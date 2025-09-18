"""
Basic Pokemon Commands
Handles core Pokemon gameplay commands like encounters and catching.
"""

import discord
from discord.ext import commands
from datetime import datetime, timedelta
from ..managers import PokemonDatabaseManager, PlayerDataManager, WildSpawnManager
from ..utils import PokemonEmbedUtils, PokemonTypeUtils


class BasicPokemonCommands:
    """Contains basic Pokemon gameplay commands"""
    
    def __init__(self, pokemon_db: PokemonDatabaseManager, player_db: PlayerDataManager, wild_spawn: WildSpawnManager):
        self.pokemon_db = pokemon_db
        self.player_db = player_db
        self.wild_spawn = wild_spawn
    
    async def encounter_pokemon(self, ctx):
        """Encounter a wild Pokemon"""
        user_id = str(ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        # Check cooldown
        if not player.can_encounter():
            cooldown_remaining = player.get_cooldown_remaining()
            
            embed = discord.Embed(
                title="⏱️ Cooldown Active",
                description=f"Please wait {cooldown_remaining + 1} more minute(s) before your next encounter.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        # Get random Pokemon
        pokemon = self.pokemon_db.get_random_pokemon_by_rarity_weights()
        if not pokemon:
            embed = discord.Embed(
                title="❌ Error",
                description="No Pokemon available for encounter. Please try again later.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Update player with encounter
        player.add_encounter(pokemon)
        self.player_db.save_player(user_id)
        
        # Create encounter embed
        player_stats = {
            'normal_balls': player.inventory.normal_pokeballs,
            'master_balls': player.inventory.master_pokeballs,
            'total_encounters': player.stats.total_encounters
        }
        
        embed = PokemonEmbedUtils.create_encounter_embed(
            pokemon=pokemon,
            player_name=ctx.author.mention,
            player_avatar_url=ctx.author.display_avatar.url,
            player_stats=player_stats
        )
        
        await ctx.send(embed=embed)
    
    async def catch_pokemon(self, ctx, ball_type: str = "normal"):
        """Attempt to catch the currently encountered Pokemon"""
        user_id = str(ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        # Check if there's a current encounter
        if not player.current_encounter:
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
        if not player.inventory.has_pokeball(ball_type):
            ball_name = "Normal Pokeballs" if ball_type == "normal" else "Master Balls"
            embed = discord.Embed(
                title="❌ No Pokeballs",
                description=f"You don't have any {ball_name} left!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Attempt to catch the Pokemon
        pokemon = player.current_encounter
        success = player.catch_pokemon(ball_type)
        self.player_db.save_player(user_id)
        
        if success:
            # Create success embed
            embed = PokemonEmbedUtils.create_catch_success_embed(
                pokemon=pokemon,
                player_name=ctx.author.mention,
                player_avatar_url=ctx.author.display_avatar.url,
                ball_type=ball_type,
                collection_id=len(player.pokemon_collection),
                total_caught=len(player.pokemon_collection)
            )
        else:
            # Create failure embed
            embed = PokemonEmbedUtils.create_catch_failure_embed(pokemon, ball_type)
        
        # Add remaining pokeball count
        remaining_normal = player.inventory.normal_pokeballs
        remaining_master = player.inventory.master_pokeballs
        ball_text = f"**{remaining_normal}** Normal Pokeballs"
        if remaining_master > 0:
            ball_text += f"\n**{remaining_master}** Master Balls"
        embed.add_field(name="Pokeballs Remaining", value=ball_text, inline=True)
        
        await ctx.send(embed=embed)
    
    async def wild_catch(self, ctx):
        """Attempt to catch the current wild Pokemon in the pokemon channel"""
        # Check if this is the pokemon channel
        if ctx.channel.name != self.wild_spawn.spawn_data.spawn_channel:
            embed = discord.Embed(
                title="❌ Wrong Channel",
                description=f"Wild Pokemon can only be caught in the #{self.wild_spawn.spawn_data.spawn_channel} channel!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        user_id = str(ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        # Check if there's a current wild Pokemon
        if not self.wild_spawn.is_wild_pokemon_available():
            embed = discord.Embed(
                title="❌ No Wild Pokemon",
                description="There's no wild Pokemon available to catch right now!\nWait for the next wild spawn (every 30 minutes).",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Check if player has pokeballs
        if not player.inventory.has_pokeball("normal"):
            embed = discord.Embed(
                title="❌ No Pokeballs",
                description="You don't have any Normal Pokeballs left! Wild Pokemon can only be caught with Normal Pokeballs.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Get the wild Pokemon
        wild_pokemon = self.wild_spawn.get_current_wild_pokemon()
        if not wild_pokemon:
            embed = discord.Embed(
                title="❌ No Wild Pokemon",
                description="There's no wild Pokemon available to catch right now!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Attempt to catch
        success = player.catch_wild_pokemon(wild_pokemon)
        self.player_db.save_player(user_id)
        
        if success:
            # Mark as caught in wild spawn system
            self.wild_spawn.mark_pokemon_caught(user_id, ctx.author.display_name)
            
            embed = discord.Embed(
                title="🎉 Pokemon Caught!",
                description=f"**Congratulations {ctx.author.mention}!**\n\nYou successfully caught the wild **{wild_pokemon.name}**!\nIt's now part of your collection.",
                color=PokemonTypeUtils.get_type_color(wild_pokemon.types)
            )
            embed.set_image(url=wild_pokemon.image_url)
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            
            # Add Pokemon info
            embed.add_field(name="Type", value=PokemonTypeUtils.format_types(wild_pokemon.types), inline=True)
            embed.add_field(name="Rarity", value=f"{wild_pokemon.rarity}", inline=True)
            embed.add_field(name="Collection ID", value=f"#{len(player.pokemon_collection)}", inline=True)
            
            # Simple achievement text
            total_caught = len(player.pokemon_collection)
            embed.add_field(name="🏆 Victory!", value=f"You caught the wild {wild_pokemon.name}!\nTotal Pokemon: {total_caught}", inline=False)
            
            embed.set_footer(text=f"Caught by {ctx.author.display_name}")
            
        else:
            embed = discord.Embed(
                title="💨 Pokemon Escaped!",
                description=f"The wild **{wild_pokemon.name}** broke free! Other trainers can still try to catch it.",
                color=discord.Color.orange()
            )
            embed.set_thumbnail(url=wild_pokemon.sprite_url)
            embed.add_field(name="Still Available", value="The Pokemon is still available for others to catch!", inline=False)
        
        # Add remaining pokeball count
        remaining_balls = player.inventory.normal_pokeballs
        embed.add_field(name="Pokeballs Remaining", value=f"{remaining_balls} Normal Pokeballs", inline=True)
        
        await ctx.send(embed=embed)
    
    async def wild_status(self, ctx):
        """Check the status of wild Pokemon spawning"""
        status = self.wild_spawn.get_spawn_status()
        
        embed = discord.Embed(
            title="🌲 Wild Pokemon Status",
            color=discord.Color.blue()
        )
        
        if status["has_wild_pokemon"]:
            pokemon_name = status.get("pokemon_name", "Unknown")
            pokemon_rarity = status.get("pokemon_rarity", "Unknown")
            spawn_time = status.get("spawn_time")
            
            if spawn_time:
                spawn_datetime = datetime.fromisoformat(spawn_time)
                time_available = datetime.now() - spawn_datetime
                minutes_available = int(time_available.total_seconds() / 60)
            else:
                minutes_available = 0
            
            embed.description = f"A wild **{pokemon_name}** is currently available!"
            embed.add_field(name="⭐ Rarity", value=pokemon_rarity, inline=True)
            embed.add_field(name="⏰ Available for", value=f"{minutes_available} minutes", inline=True)
            embed.add_field(name="📍 Location", value=f"#{status['spawn_channel']} channel", inline=True)
            embed.add_field(name="🎯 How to Catch", value="Use `!wild_catch` in the pokemon channel!", inline=True)
            
        elif "caught_by" in status:
            caught_info = status["caught_by"]
            embed.description = f"The wild Pokemon was already caught!"
            embed.add_field(name="🏆 Caught by", value=caught_info["username"], inline=True)
            embed.add_field(name="⏰ Caught", value="Recently", inline=True)
            embed.add_field(name="🔄 Next Spawn", value="Wait for next 30-minute cycle", inline=True)
        else:
            embed.description = "No wild Pokemon is currently available."
            embed.add_field(name="⏰ Next Spawn", value="Check back later - spawns every 30 minutes!", inline=True)
            embed.add_field(name="📍 Spawn Location", value=f"#{status['spawn_channel']} channel", inline=True)
        
        # Show last spawn time
        if status.get("last_spawn"):
            last_spawn = datetime.fromisoformat(status["last_spawn"])
            time_since = datetime.now() - last_spawn
            embed.add_field(name="🕐 Last Spawn", value=f"{int(time_since.total_seconds() / 60)} minutes ago", inline=True)
        
        await ctx.send(embed=embed)