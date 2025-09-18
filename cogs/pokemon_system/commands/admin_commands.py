"""
Admin Pokemon Commands
Handles administrative commands for Pokemon system management.
"""

import discord
from ..managers import PokemonDatabaseManager, PlayerDataManager, WildSpawnManager
from ..utils import ErrorUtils
from config import Config


class AdminPokemonCommands:
    """Contains administrative Pokemon commands"""
    
    def __init__(self, pokemon_db: PokemonDatabaseManager, player_db: PlayerDataManager, wild_spawn: WildSpawnManager):
        self.pokemon_db = pokemon_db
        self.player_db = player_db
        self.wild_spawn = wild_spawn
    
    async def pokemon_admin(self, ctx):
        """Admin command to view Pokemon database statistics"""
        if not Config.is_admin(ctx.author.id):
            embed = ErrorUtils.create_system_error_embed("You don't have permission to use admin commands.")
            embed.title = "❌ Access Denied"
            await ctx.send(embed=embed)
            return
        
        # Get database statistics
        db_stats = self.pokemon_db.get_database_stats()
        player_stats = self.player_db.get_player_stats_summary()
        
        embed = discord.Embed(
            title="🔧 Pokemon Database Admin Panel",
            description="Database Statistics and Management",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📊 Total Pokemon", 
            value=f"**{db_stats['total_pokemon']}** Pokemon in database\n*Target: 1025+ Pokemon*", 
            inline=False
        )
        
        # Generation breakdown
        gen_text = ""
        for gen in sorted(db_stats['generation_counts'].keys()):
            count = db_stats['generation_counts'][gen]
            gen_text += f"**Generation {gen}:** {count} Pokemon\n"
        
        embed.add_field(name="🌍 By Generation", value=gen_text, inline=True)
        
        # Rarity breakdown
        rarity_text = ""
        for rarity, count in db_stats['rarity_counts'].items():
            percentage = (count / db_stats['total_pokemon'] * 100) if db_stats['total_pokemon'] > 0 else 0
            rarity_text += f"**{rarity}:** {count} ({percentage:.1f}%)\n"
        
        embed.add_field(name="⭐ By Rarity", value=rarity_text, inline=True)
        
        # Player statistics
        embed.add_field(
            name="👥 Player Stats",
            value=f"**Active Players:** {player_stats['total_players']}\n**Total Pokemon Caught:** {player_stats['total_pokemon_caught']}",
            inline=True
        )
        
        # Database status
        available_gens = self.pokemon_db.available_generations
        missing_gens = []
        max_gen = max(available_gens) if available_gens else 0
        for gen in range(1, 10):  # Generations 1-9
            if gen not in available_gens:
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
        
        # Validate ball type using ValidationUtils
        from ..utils.validation_utils import ValidationUtils
        is_valid, error_message = ValidationUtils.validate_ball_type(ball_type)
        if not is_valid:
            embed = discord.Embed(
                title="❌ Invalid Ball Type",
                description=f"Valid ball types are: poke, great, ultra, master",
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
        
        # Get player and add pokeballs
        user_id = str(user.id)
        player = self.player_db.get_player(user_id)
        
        # Normalize ball type
        normalized_ball_type = player.inventory._normalize_ball_type(ball_type)
        ball_info = player.inventory.get_ball_info(normalized_ball_type)
        
        player.inventory.add_pokeballs(normalized_ball_type, count)
        self.player_db.save_player(user_id)
        
        # Create confirmation embed with proper ball name and icon
        ball_name = ball_info.get("name", ball_type.title() + " Ball")
        ball_icon = ball_info.get("icon", "⚾")
        
        embed = discord.Embed(
            title="✅ Pokeballs Given",
            description=f"Successfully gave {count} {ball_name}(s) to {user.mention}!",
            color=discord.Color.green()
        )
        
        # Show user's current pokeball inventory
        all_balls = player.inventory.get_all_balls()
        inventory_text = ""
        for ball_type_key, ball_data in all_balls.items():
            if ball_data["count"] > 0:
                inventory_text += f"{ball_data['name']}: {ball_data['count']}\n"
        
        if not inventory_text:
            inventory_text = "No pokeballs"
        
        embed.add_field(
            name=f"🎒 {user.display_name}'s Pokeball Inventory",
            value=inventory_text,
            inline=False
        )
        
        embed.add_field(
            name="📋 Action Details",
            value=f"**Given:** {count} {ball_name}(s)\n**To:** {user.display_name}\n**By:** {ctx.author.display_name}",
            inline=True
        )
        
        embed.set_footer(text=f"Admin Action | Executed by {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
    
    async def give_pokecoins(self, ctx, user: discord.Member, amount: int):
        """Admin command to give PokéCoins to a user"""
        if not Config.is_admin(ctx.author.id):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use admin commands.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Validate amount
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be a positive number.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Get player and add PokéCoins
        user_id = str(user.id)
        player = self.player_db.get_player(user_id)
        
        old_balance = player.pokecoins
        new_balance = player.add_pokecoins(amount)
        self.player_db.save_player(user_id)
        
        # Create confirmation embed
        embed = discord.Embed(
            title="💰 PokéCoins Given",
            description=f"Successfully gave {amount:,} PokéCoins to {user.mention}!",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="💳 Balance Update",
            value=f"**Previous:** {old_balance:,} PokéCoins\n**Added:** +{amount:,} PokéCoins\n**New Balance:** {new_balance:,} PokéCoins",
            inline=False
        )
        
        embed.add_field(
            name="📋 Action Details",
            value=f"**Given:** {amount:,} PokéCoins\n**To:** {user.display_name}\n**By:** {ctx.author.display_name}",
            inline=True
        )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Admin Action | Executed by {ctx.author.display_name}")
        
        await ctx.send(embed=embed)
    
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
        
        # This will need to be called from the main cog with bot reference
        success = await self.wild_spawn.force_spawn(ctx.bot, self.pokemon_db)
        
        if success:
            embed = discord.Embed(
                title="✅ Wild Spawn Triggered",
                description=f"A wild Pokemon has been manually spawned in #{self.wild_spawn.spawn_data.spawn_channel}!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Spawn Failed",
                description="Failed to trigger wild spawn. Check logs for details.",
                color=discord.Color.red()
            )
        
        embed.set_footer(text=f"Triggered by {ctx.author.display_name}")
        await ctx.send(embed=embed)
    
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
        
        target_channel = self.wild_spawn.spawn_data.spawn_channel
        embed.add_field(
            name="🎯 Target Channel",
            value=f"Looking for: `{target_channel}`",
            inline=False
        )
        
        # Check each guild
        for guild in ctx.bot.guilds:
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