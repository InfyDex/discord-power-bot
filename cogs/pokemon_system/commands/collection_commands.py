"""
Collection Pokemon Commands
Handles commands related to viewing and managing Pokemon collections.
"""

import discord
from discord.ext import commands
from datetime import datetime
from ..managers import PokemonDatabaseManager, PlayerDataManager
from ..utils import PokemonEmbedUtils, PokemonTypeUtils


class CollectionPokemonCommands:
    """Contains Pokemon collection management commands"""
    
    def __init__(self, pokemon_db: PokemonDatabaseManager, player_db: PlayerDataManager):
        self.pokemon_db = pokemon_db
        self.player_db = player_db
    
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
        
        player = self.player_db.get_player(user_id)
        
        if not player.pokemon_collection:
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
        embed = PokemonEmbedUtils.create_collection_embed(
            player_name=user.display_name,
            pokemon_collection=player.pokemon_collection,
            is_own_collection=is_own_collection
        )
        
        await ctx.send(embed=embed)
    
    async def pokemon_stats(self, ctx):
        """View your Pokemon game statistics"""
        user_id = str(ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        embed = discord.Embed(
            title=f"📊 {ctx.author.display_name}'s Pokemon Stats",
            color=discord.Color.purple()
        )
        
        embed.add_field(name="🏆 Pokemon Caught", value=str(len(player.pokemon_collection)), inline=True)
        embed.add_field(name="👁️ Total Encounters", value=str(player.stats.total_encounters), inline=True)
        embed.add_field(name="⚾ Pokeballs Left", value=str(player.inventory.normal_pokeballs), inline=True)
        
        if player.stats.total_encounters > 0:
            catch_rate = player.stats.get_catch_rate()
            embed.add_field(name="🎯 Catch Rate", value=f"{catch_rate:.1f}%", inline=True)
        
        join_date = datetime.fromisoformat(player.stats.join_date).strftime("%B %d, %Y")
        embed.add_field(name="📅 Trainer Since", value=join_date, inline=True)
        
        await ctx.send(embed=embed)
    
    async def pokemon_inventory(self, ctx):
        """View your Pokemon inventory and items"""
        user_id = str(ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        # Create inventory embed
        embed = discord.Embed(
            title=f"🎒 {ctx.author.display_name}'s Inventory",
            description="Your Pokemon trainer inventory and items",
            color=discord.Color.green()
        )
        
        # Add user avatar
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        
        # Pokeballs section
        normal_balls = player.inventory.normal_pokeballs
        master_balls = player.inventory.master_pokeballs
        
        pokeball_text = f"⚾ **Normal Pokeballs:** {normal_balls}\n🌟 **Master Balls:** {master_balls}"
        total_balls = normal_balls + master_balls
        pokeball_text += f"\n📊 **Total Pokeballs:** {total_balls}"
        
        embed.add_field(
            name="⚾ Pokeballs", 
            value=pokeball_text, 
            inline=True
        )
        
        # Pokemon collection summary
        pokemon_count = len(player.pokemon_collection)
        if pokemon_count > 0:
            # Get rarity breakdown
            rarity_breakdown = player.get_collection_by_rarity()
            
            collection_text = f"🏆 **Total Pokemon:** {pokemon_count}\n"
            collection_text += f"🟡 **Legendary:** {len(rarity_breakdown['Legendary'])}\n"
            collection_text += f"🔵 **Rare:** {len(rarity_breakdown['Rare'])}\n"
            collection_text += f"🟢 **Uncommon:** {len(rarity_breakdown['Uncommon'])}\n"
            collection_text += f"⚪ **Common:** {len(rarity_breakdown['Common'])}"
        else:
            collection_text = "🏆 **Total Pokemon:** 0\nNo Pokemon caught yet!"
        
        embed.add_field(
            name="📖 Pokemon Collection", 
            value=collection_text, 
            inline=True
        )
        
        # Trainer stats
        total_encounters = player.stats.total_encounters
        total_caught = player.stats.total_caught
        catch_rate = player.stats.get_catch_rate()
        
        stats_text = f"👁️ **Encounters:** {total_encounters}\n"
        stats_text += f"🎯 **Catch Rate:** {catch_rate:.1f}%\n"
        
        # Join date
        join_date = datetime.fromisoformat(player.stats.join_date).strftime("%B %d, %Y")
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
        if player.current_encounter:
            footer_text = f"🌿 Active Encounter: {player.current_encounter.name} | Ready to catch!"
        else:
            # Check cooldown
            if player.can_encounter():
                footer_text = "✅ Ready for next encounter!"
            else:
                cooldown_remaining = player.get_cooldown_remaining()
                footer_text = f"⏰ Next encounter in {cooldown_remaining + 1} minute(s)"
        
        embed.set_footer(text=footer_text)
        
        await ctx.send(embed=embed)
    
    async def pokemon_info(self, ctx, *, pokemon_identifier):
        """View detailed information about a specific Pokemon in your collection"""
        user_id = str(ctx.author.id)
        player = self.player_db.get_player(user_id)
        
        if not player.pokemon_collection:
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
            found_pokemon = player.get_pokemon_by_id(pokemon_id)
        else:
            # Search by name
            found_pokemon = player.get_pokemon_by_name(pokemon_identifier)
        
        if not found_pokemon:
            embed = discord.Embed(
                title="❌ Pokemon Not Found",
                description=f"Could not find Pokemon '{pokemon_identifier}' in your collection.\nUse `!collection` to see all your Pokemon.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Create detailed Pokemon info embed
        embed = PokemonEmbedUtils.create_pokemon_detail_embed(found_pokemon, ctx.author.display_name)
        
        await ctx.send(embed=embed)