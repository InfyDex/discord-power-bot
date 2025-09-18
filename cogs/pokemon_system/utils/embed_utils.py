"""
Pokemon Embed Utilities  
Helper functions for creating Pokemon-related Discord embeds.
"""

import discord
from typing import List, Dict
from datetime import datetime

from .type_utils import PokemonTypeUtils
from ..models.pokemon_model import PokemonData, CaughtPokemon


class PokemonEmbedUtils:
    """Utilities for creating Pokemon-related Discord embeds"""
    
    @staticmethod
    def create_wild_spawn_embed(pokemon: PokemonData) -> discord.Embed:
        """Create embed for wild Pokemon spawn"""
        embed = discord.Embed(
            title=f"🌿 A Wild {pokemon.name} Appeared!",
            description=f"A wild **{pokemon.name}** has appeared! First trainer to catch it wins!\n\n**Type `!wild_catch` to attempt capture**\n\n*{pokemon.description}*",
            color=PokemonTypeUtils.get_type_color(pokemon.types)
        )
        
        # Add Pokemon image
        embed.set_image(url=pokemon.image_url)
        embed.set_thumbnail(url=pokemon.sprite_url)
        
        # Format types
        type_text = PokemonTypeUtils.format_types(pokemon.types)
        embed.add_field(name="Type", value=f"{type_text}", inline=True)
        embed.add_field(name="Rarity", value=f"{pokemon.rarity}", inline=True)
        embed.add_field(name="Catch Rate", value=f"{int(pokemon.catch_rate * 100)}%", inline=True)
        
        # Add Pokedex and generation info
        embed.add_field(name="Pokedex #", value=f"#{pokemon.id}", inline=True)
        embed.add_field(name="Generation", value=f"Gen {pokemon.generation}", inline=True)
        embed.add_field(name="Total Stats", value=f"{pokemon.stats.total}", inline=True)
        
        # Clean stats display
        stats = pokemon.stats
        stats_text = f"**HP:** {stats.hp} | **ATK:** {stats.attack} | **DEF:** {stats.defense}\n**SP.ATK:** {stats.sp_attack} | **SP.DEF:** {stats.sp_defense} | **SPD:** {stats.speed}"
        embed.add_field(name="📊 Base Stats", value=stats_text, inline=False)
        
        # Simple competition info
        embed.add_field(
            name="🎯 How to Catch", 
            value="Type `!wild_catch` to attempt capture!\nFirst successful trainer wins this Pokemon.", 
            inline=False
        )
        
        # Simple footer
        embed.set_footer(text=f"Wild Pokemon Event • Gen {pokemon.generation} • Next spawn in 30 minutes")
        embed.set_author(name="Legion Pokemon", icon_url="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/poke-ball.png")
        
        return embed
    
    @staticmethod
    def create_encounter_embed(pokemon: PokemonData, player_name: str, player_avatar_url: str, encounter_type: str = "encounter") -> discord.Embed:
        """Create embed for personal Pokemon encounter"""
        embed = discord.Embed(
            title=f"🌿 Wild {pokemon.name} Appeared!",
            description=f"**{player_name}** encountered a wild **{pokemon.name}**!\n\n*{pokemon.description}*\n\n**This is your personal encounter - only you can catch it!**",
            color=PokemonTypeUtils.get_type_color(pokemon.types)
        )
        
        # Add Pokemon image
        embed.set_image(url=pokemon.image_url)
        embed.set_thumbnail(url=player_avatar_url)
        
        # Format types
        type_text = PokemonTypeUtils.format_types(pokemon.types)
        embed.add_field(name="Type", value=f"{type_text}", inline=True)
        embed.add_field(name="Rarity", value=f"{pokemon.rarity}", inline=True)
        embed.add_field(name="Catch Rate", value=f"{int(pokemon.catch_rate * 100)}%", inline=True)
        
        # Add ID and generation info
        embed.add_field(name="Pokedex #", value=f"#{pokemon.id}", inline=True)
        embed.add_field(name="Generation", value=f"Gen {pokemon.generation}", inline=True)
        embed.add_field(name="Total Stats", value=f"{pokemon.stats.total}", inline=True)
        
        # Add stats preview - clean format
        stats = pokemon.stats
        stats_text = f"**HP:** {stats.hp} | **ATK:** {stats.attack} | **DEF:** {stats.defense}\n**SP.ATK:** {stats.sp_attack} | **SP.DEF:** {stats.sp_defense} | **SPD:** {stats.speed}"
        embed.add_field(name="📊 Base Stats", value=stats_text, inline=False)
        
        # Simple capture instructions
        embed.add_field(name="🎯 How to Catch", value="Use `!catch normal` or `!catch master` to attempt capture!", inline=False)
        
        # Clean footer
        embed.set_footer(text=f"Personal encounter for {player_name} • Gen {pokemon.generation} • Use !catch to capture")
        embed.set_author(name="Legion Pokemon", icon_url="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/poke-ball.png")
        
        return embed
    
    @staticmethod
    def create_catch_success_embed(pokemon: PokemonData, player_name: str, player_avatar_url: str, ball_type: str, collection_id: int, total_caught: int) -> discord.Embed:
        """Create embed for successful Pokemon catch"""
        embed = discord.Embed(
            title="🎉 Pokemon Caught!",
            description=f"**Congratulations {player_name}!**\n\nYou successfully caught **{pokemon.name}**!\nIt's now part of your collection.",
            color=PokemonTypeUtils.get_type_color(pokemon.types)
        )
        embed.set_image(url=pokemon.image_url)
        embed.set_thumbnail(url=player_avatar_url)
        
        # Add Pokemon info
        embed.add_field(name="Type", value=PokemonTypeUtils.format_types(pokemon.types), inline=True)
        embed.add_field(name="Rarity", value=f"{pokemon.rarity}", inline=True)
        embed.add_field(name="Collection ID", value=f"#{collection_id}", inline=True)
        
        # Add capture details
        ball_emoji = "⚾" if ball_type == "normal" else "🌟"
        ball_name = "Normal Pokeball" if ball_type == "normal" else "Master Ball"
        embed.add_field(name=f"{ball_emoji} Caught With", value=f"{ball_name}", inline=True)
        embed.add_field(name="Source", value="Personal Encounter", inline=True)
        embed.add_field(name="Generation", value=f"Gen {pokemon.generation}", inline=True)
        
        # Simple collection info
        embed.add_field(name="🏆 Collection Progress", value=f"Total Pokemon: {total_caught}", inline=False)
        
        embed.set_footer(text=f"Caught by {player_name}")
        embed.set_author(name="Legion Pokemon", icon_url="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/poke-ball.png")
        
        return embed
    
    @staticmethod
    def create_catch_failure_embed(pokemon: PokemonData, ball_type: str, remaining_pokeballs: int) -> discord.Embed:
        """Create embed for failed Pokemon catch"""
        ball_name = "Normal Pokeball" if ball_type == "normal" else "Master Ball"
        
        embed = discord.Embed(
            title="💨 Pokemon Escaped!",
            description=f"**{pokemon.name}** broke free from the {ball_name} and escaped!\n\nTry encountering another Pokemon with `!encounter`.",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=pokemon.sprite_url)
        embed.add_field(name="Next Steps", value=f"• Use `!encounter` to find another Pokemon\n• Try using a Master Ball for guaranteed success\n• This Pokemon had a {int(pokemon.catch_rate * 100)}% catch rate", inline=False)
        embed.add_field(name=f"{ball_name}s Remaining", value=f"{remaining_pokeballs}", inline=True)
        
        return embed
    
    @staticmethod
    def create_collection_embed(player_name: str, pokemon_collection: List[CaughtPokemon], is_own_collection: bool = True) -> discord.Embed:
        """Create embed for Pokemon collection display"""
        title = f"📖 {player_name}'s Collection" if is_own_collection else f"📖 {player_name}'s Collection"
        
        embed = discord.Embed(
            title=title,
            description=f"**Total Pokemon:** {len(pokemon_collection)}",
            color=discord.Color.blue()
        )
        
        if not pokemon_collection:
            if is_own_collection:
                embed.description = "You haven't caught any Pokemon yet!\nUse `!encounter` to find wild Pokemon."
            else:
                embed.description = f"{player_name} hasn't caught any Pokemon yet!"
            return embed
        
        # Group Pokemon by rarity
        by_rarity = {"Common": [], "Uncommon": [], "Rare": [], "Legendary": []}
        for pokemon in pokemon_collection:
            rarity = pokemon.rarity
            if rarity in by_rarity:
                by_rarity[rarity].append(pokemon)
        
        # Add Pokemon by rarity (simplified)
        for rarity in ["Legendary", "Rare", "Uncommon", "Common"]:
            if by_rarity[rarity]:
                pokemon_names = []
                for p in by_rarity[rarity]:
                    type_text = PokemonTypeUtils.format_types(p.types)
                    pokemon_names.append(f"**#{p.collection_id} {p.name}** ({type_text})")
                
                display_names = pokemon_names[:6]  # Show fewer Pokemon for cleaner display
                if len(pokemon_names) > 6:
                    display_names.append(f"*... and {len(pokemon_names) - 6} more*")
                
                rarity_emoji = PokemonTypeUtils.get_rarity_emoji(rarity)
                embed.add_field(
                    name=f"{rarity_emoji} {rarity} ({len(by_rarity[rarity])})",
                    value="\n".join(display_names),
                    inline=False
                )
        
        # Simple collection stats
        wild_caught = len([p for p in pokemon_collection if p.caught_from == 'wild_spawn'])
        encounter_caught = len([p for p in pokemon_collection if p.caught_from != 'wild_spawn'])
        
        # Generation breakdown
        gen_count = {}
        for p in pokemon_collection:
            gen = p.generation
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
        if pokemon_collection:
            # Find the most recent Pokemon
            display_pokemon = max(pokemon_collection, key=lambda x: x.caught_date)
            
            # Set the image
            embed.set_image(url=display_pokemon.image_url)
            embed.set_footer(text=f"Showing {display_pokemon.name} • {player_name}")
        
        return embed
    
    @staticmethod
    def create_pokemon_detail_embed(pokemon: CaughtPokemon, player_name: str) -> discord.Embed:
        """Create detailed embed for a specific Pokemon"""
        embed = discord.Embed(
            title=f"📋 {pokemon.name} - Details",
            description=pokemon.description,
            color=PokemonTypeUtils.get_type_color(pokemon.types)
        )
        
        # Add Pokemon image
        embed.set_image(url=pokemon.image_url)
        embed.set_thumbnail(url=pokemon.sprite_url)
        
        # Basic info
        embed.add_field(name="🆔 Collection ID", value=f"#{pokemon.collection_id}", inline=True)
        embed.add_field(name="🏷️ Type", value=PokemonTypeUtils.format_types(pokemon.types), inline=True)
        embed.add_field(name="⭐ Rarity", value=pokemon.rarity, inline=True)
        
        # Caught date
        caught_date = datetime.fromisoformat(pokemon.caught_date).strftime("%B %d, %Y at %I:%M %p")
        embed.add_field(name="📅 Caught On", value=caught_date, inline=True)
        
        # Generation info
        embed.add_field(name="🌍 Generation", value=f"Gen {pokemon.generation}", inline=True)
        embed.add_field(name="📊 Base Stat Total", value=pokemon.stats.total, inline=True)
        
        # Detailed stats
        stats = pokemon.stats
        stats_text = (
            f"**HP:** {stats.hp} | **Attack:** {stats.attack} | **Defense:** {stats.defense}\n"
            f"**Sp. Attack:** {stats.sp_attack} | **Sp. Defense:** {stats.sp_defense} | **Speed:** {stats.speed}"
        )
        embed.add_field(name="📊 Base Stats", value=stats_text, inline=False)
        
        embed.set_footer(text=f"Requested by {player_name}")
        
        return embed