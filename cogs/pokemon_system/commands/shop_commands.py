"""
Shop Commands
Handles shop functionality for purchasing pokeballs with pokecoins.
"""

import discord
from typing import Dict, List

from ..managers import PokemonDatabaseManager, PlayerDataManager
from ..utils import PokemonEmbedUtils
from ..utils.interaction_utils import UnifiedContext, create_unified_context
from ..models.player_model import PlayerInventory
from config import Config


class ShopCommands:
    """Contains shop-related commands for purchasing items with pokecoins"""
    
    # Shop item configurations with prices
    SHOP_ITEMS = {
        "poke": {
            "price": 100,
            "display_name": "Poké Ball",
            "description": "Basic pokeball with standard catch rate"
        },
        "great": {
            "price": 1000,
            "display_name": "Great Ball", 
            "description": "Enhanced pokeball with 1.5x catch rate"
        },
        "ultra": {
            "price": 10000,
            "display_name": "Ultra Ball",
            "description": "Advanced pokeball with 2x catch rate"
        },
        "master": {
            "price": 50000,
            "display_name": "Master Ball",
            "description": "Legendary pokeball with guaranteed catch"
        }
    }
    
    def __init__(self, pokemon_db: PokemonDatabaseManager, player_db: PlayerDataManager):
        self.pokemon_db = pokemon_db
        self.player_db = player_db
        
        # Setup logging
        self.logger = Config.setup_logging()
    
    async def show_shop(self, ctx):
        """Display the pokeball shop with all available items"""
        try:
            unified_ctx = create_unified_context(ctx)
            user_id = str(unified_ctx.author.id)
            player = self.player_db.get_player(user_id)
            
            # Create shop embed
            embed = discord.Embed(
                title="🏪 Pokéball Shop",
                description=f"Your PokéCoins: **{player.pokecoins:,}** 💰",
                color=0x00ff00
            )
            
            # Add each shop item as a field
            for ball_type, config in self.SHOP_ITEMS.items():
                ball_config = PlayerInventory.POKEBALL_CONFIG[ball_type]
                price = config["price"]
                
                # Format catch rate info
                catch_rate = ball_config["catch_rate_modifier"]
                if catch_rate == float('inf'):
                    catch_info = "Guaranteed Catch"
                else:
                    catch_info = f"{catch_rate}x Catch Rate"
                
                # Check if player can afford it
                affordable = "✅" if player.pokecoins >= price else "❌"
                
                embed.add_field(
                    name=f"{affordable} {config['display_name']}",
                    value=f"**Price:** {price:,} PokéCoins\n"
                          f"**Effect:** {catch_info}\n"
                          f"*{config['description']}*",
                    inline=True
                )
            
            # Add thumbnail
            embed.set_thumbnail(url="https://archives.bulbagarden.net/media/upload/b/b3/Pok%C3%A9_Ball_ZA_Art.png")
            
            # Add footer with usage instructions
            embed.set_footer(text="Use /buy <pokeball_type> <quantity> to purchase items!")
            
            await unified_ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in show_shop: {str(e)}")
            error_embed = discord.Embed(
                title="❌ Shop Error",
                description="Something went wrong while loading the shop. Please try again.",
                color=0xff0000
            )
            await unified_ctx.send(embed=error_embed)
    
    async def buy_pokeball(self, ctx, ball_type: str, quantity: int = 1):
        """Purchase pokeballs from the shop"""
        try:
            unified_ctx = create_unified_context(ctx)
            user_id = str(unified_ctx.author.id)
            player = self.player_db.get_player(user_id)
            
            # Normalize ball type
            ball_type = ball_type.lower()
            if ball_type == "pokeball" or ball_type == "normal":
                ball_type = "poke"
            
            # Validate ball type
            if ball_type not in self.SHOP_ITEMS:
                valid_types = ", ".join(self.SHOP_ITEMS.keys())
                embed = discord.Embed(
                    title="❌ Invalid Item",
                    description=f"Invalid pokeball type: `{ball_type}`\n"
                               f"Valid types: {valid_types}",
                    color=0xff0000
                )
                await unified_ctx.send(embed=embed)
                return
            
            # Validate quantity
            if quantity <= 0:
                embed = discord.Embed(
                    title="❌ Invalid Quantity", 
                    description="Quantity must be a positive number!",
                    color=0xff0000
                )
                await unified_ctx.send(embed=embed)
                return
            
            if quantity > 100:
                embed = discord.Embed(
                    title="❌ Quantity Limit",
                    description="You can only buy up to 100 pokeballs at once!",
                    color=0xff0000
                )
                await unified_ctx.send(embed=embed)
                return
            
            # Calculate total cost
            item_config = self.SHOP_ITEMS[ball_type]
            total_cost = item_config["price"] * quantity
            
            # Check if player has enough pokecoins
            if player.pokecoins < total_cost:
                embed = discord.Embed(
                    title="❌ Insufficient Funds",
                    description=f"You need **{total_cost:,}** PokéCoins but only have **{player.pokecoins:,}**!\n"
                               f"Shortfall: **{total_cost - player.pokecoins:,}** PokéCoins",
                    color=0xff0000
                )
                await unified_ctx.send(embed=embed)
                return
            
            # Process the purchase
            if player.spend_pokecoins(total_cost):
                player.inventory.add_pokeballs(ball_type, quantity)
                self.player_db.save_player(user_id)
                
                # Get ball configuration for display
                ball_config = PlayerInventory.POKEBALL_CONFIG[ball_type]
                
                # Create success embed
                embed = discord.Embed(
                    title="✅ Purchase Successful!",
                    description=f"Successfully purchased **{quantity}x {item_config['display_name']}**!",
                    color=0x00ff00
                )
                
                embed.add_field(
                    name="💰 Transaction Details",
                    value=f"**Cost:** {total_cost:,} PokéCoins\n"
                          f"**Remaining Balance:** {player.pokecoins:,} PokéCoins",
                    inline=False
                )
                
                embed.add_field(
                    name="🎒 Updated Inventory",
                    value=f"**{item_config['display_name']}:** {player.inventory.get_pokeball_count(ball_type)}",
                    inline=False
                )
                
                # Set thumbnail to the purchased pokeball
                embed.set_thumbnail(url=ball_config["icon"])
                
                await unified_ctx.send(embed=embed)
                
                # Log the purchase
                self.logger.info(f"Player {user_id} bought {quantity}x {ball_type} for {total_cost} pokecoins")
                
            else:
                # This shouldn't happen if our checks above work, but just in case
                embed = discord.Embed(
                    title="❌ Purchase Failed",
                    description="Something went wrong with the purchase. Please try again.",
                    color=0xff0000
                )
                await unified_ctx.send(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error in buy_pokeball: {str(e)}")
            error_embed = discord.Embed(
                title="❌ Purchase Error",
                description="Something went wrong while processing your purchase. Please try again.",
                color=0xff0000
            )
            await unified_ctx.send(embed=error_embed)