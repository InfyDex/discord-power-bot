"""
Leaderboard commands for Pokemon system.
Handles different types of leaderboards with shared logic for both prefix and slash commands.
"""

import discord
from discord.ext import commands
from typing import Dict, List, Tuple, Optional
import json
import os
from ..utils.interaction_utils import create_unified_context
from ..models.player_model import PlayerData


class LeaderboardCommands:
    """Handles all leaderboard-related commands with shared logic"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'pokemon_data.json')
        self.pokemon_db_file = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'pokemon_master_database.json')
    
    def _load_data(self) -> Dict:
        """Load player data from JSON file"""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _load_pokemon_db(self) -> Dict:
        """Load Pokemon database for rarity calculations"""
        try:
            with open(self.pokemon_db_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _calculate_pokemon_count(self, player_data: Dict) -> int:
        """Calculate total Pokemon count for a player"""
        return len(player_data.get('pokemon', []))
    
    def _calculate_total_power(self, player_data: Dict, pokemon_db: Dict) -> int:
        """Calculate total power level of all Pokemon for a player"""
        total_power = 0
        for pokemon in player_data.get('pokemon', []):
            pokemon_name = pokemon.get('name', '')
            if pokemon_name in pokemon_db:
                # Use attack + defense + hp as power metric
                stats = pokemon_db[pokemon_name].get('stats', {})
                power = (
                    stats.get('attack', 0) + 
                    stats.get('defense', 0) + 
                    stats.get('hp', 0)
                )
                total_power += power
        return total_power
    
    def _calculate_rarity_score(self, player_data: Dict, pokemon_db: Dict) -> int:
        """Calculate rarity score based on legendary and rare Pokemon"""
        rarity_score = 0
        for pokemon in player_data.get('pokemon', []):
            pokemon_name = pokemon.get('name', '')
            if pokemon_name in pokemon_db:
                pokemon_info = pokemon_db[pokemon_name]
                # Legendary Pokemon worth 100 points
                if pokemon_info.get('legendary', False):
                    rarity_score += 100
                # Mythical Pokemon worth 150 points
                elif pokemon_info.get('mythical', False):
                    rarity_score += 150
                # Base stats above 600 worth extra points (pseudo-legendary)
                else:
                    stats = pokemon_info.get('stats', {})
                    total_stats = sum(stats.values()) if stats else 0
                    if total_stats >= 600:
                        rarity_score += 50
                    elif total_stats >= 500:
                        rarity_score += 25
        return rarity_score
    
    def _get_leaderboard_data(self, leaderboard_type: str) -> List[Tuple[str, int, str]]:
        """Get leaderboard data for specified type"""
        data = self._load_data()
        pokemon_db = self._load_pokemon_db()
        leaderboard = []
        
        for user_id, player_data in data.items():
            try:
                # Get user from bot cache
                user = self.bot.get_user(int(user_id))
                username = user.display_name if user else f"User {user_id}"
                
                if leaderboard_type == "pokemon_count":
                    score = self._calculate_pokemon_count(player_data)
                    metric = "Pokemon"
                elif leaderboard_type == "total_power":
                    score = self._calculate_total_power(player_data, pokemon_db)
                    metric = "Power"
                elif leaderboard_type == "rarity_score":
                    score = self._calculate_rarity_score(player_data, pokemon_db)
                    metric = "Rarity Score"
                else:
                    continue
                
                if score > 0:  # Only include players with actual data
                    leaderboard.append((username, score, metric))
            except Exception:
                continue  # Skip invalid entries
        
        # Sort by score (descending)
        leaderboard.sort(key=lambda x: x[1], reverse=True)
        return leaderboard[:10]  # Top 10 only
    
    def _get_user_rank(self, user_id: str, leaderboard_type: str) -> Tuple[int, int, str]:
        """Get individual user's rank in specified leaderboard"""
        data = self._load_data()
        pokemon_db = self._load_pokemon_db()
        all_scores = []
        
        for uid, player_data in data.items():
            if leaderboard_type == "pokemon_count":
                score = self._calculate_pokemon_count(player_data)
            elif leaderboard_type == "total_power":
                score = self._calculate_total_power(player_data, pokemon_db)
            elif leaderboard_type == "rarity_score":
                score = self._calculate_rarity_score(player_data, pokemon_db)
            else:
                return 0, 0, "Unknown"
            
            all_scores.append((uid, score))
        
        # Sort by score (descending)
        all_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Find user's position
        user_score = 0
        user_rank = 0
        metric = {
            "pokemon_count": "Pokemon",
            "total_power": "Power",
            "rarity_score": "Rarity Score"
        }.get(leaderboard_type, "Score")
        
        for i, (uid, score) in enumerate(all_scores):
            if uid == user_id:
                user_rank = i + 1
                user_score = score
                break
        
        return user_rank, user_score, metric
    
    def _create_leaderboard_embed(self, leaderboard_data: List[Tuple[str, int, str]], 
                                 title: str, description: str) -> discord.Embed:
        """Create a formatted embed for leaderboard display"""
        embed = discord.Embed(
            title=f"🏆 {title}",
            description=description,
            color=discord.Color.gold()
        )
        
        if not leaderboard_data:
            embed.add_field(
                name="No Data",
                value="No players found for this leaderboard.",
                inline=False
            )
            return embed
        
        # Add rankings
        leaderboard_text = ""
        medals = ["🥇", "🥈", "🥉"]
        
        for i, (username, score, metric) in enumerate(leaderboard_data):
            if i < 3:
                medal = medals[i]
            else:
                medal = f"**{i+1}.**"
            
            leaderboard_text += f"{medal} **{username}** - {score:,} {metric}\n"
        
        embed.add_field(
            name="Top 10 Rankings",
            value=leaderboard_text,
            inline=False
        )
        
        embed.set_footer(text="Use leaderboard rank @user to check individual rankings!")
        return embed
    
    def _create_rank_embed(self, user: discord.Member, rank: int, score: int, 
                          metric: str, leaderboard_type: str) -> discord.Embed:
        """Create embed for individual rank display"""
        type_names = {
            "pokemon_count": "Pokemon Collection",
            "total_power": "Total Power",
            "rarity_score": "Rarity Score"
        }
        
        embed = discord.Embed(
            title=f"📊 {type_names.get(leaderboard_type, 'Ranking')}",
            color=discord.Color.blue()
        )
        
        if rank == 0:
            embed.add_field(
                name=f"{user.display_name}'s Ranking",
                value="Not ranked (no data available)",
                inline=False
            )
        else:
            # Add rank emoji based on position
            if rank == 1:
                rank_display = "🥇 #1"
            elif rank == 2:
                rank_display = "🥈 #2"
            elif rank == 3:
                rank_display = "🥉 #3"
            else:
                rank_display = f"#{rank}"
            
            embed.add_field(
                name=f"{user.display_name}'s Ranking",
                value=f"**Rank:** {rank_display}\n**{metric}:** {score:,}",
                inline=False
            )
        
        return embed

    # Shared logic functions for different leaderboard types
    async def _leaderboard_pokemon_logic(self, unified_ctx):
        """Shared logic for Pokemon count leaderboard"""
        leaderboard_data = self._get_leaderboard_data("pokemon_count")
        embed = self._create_leaderboard_embed(
            leaderboard_data,
            "Pokemon Collection Leaderboard",
            "Top 10 players by total Pokemon collected"
        )
        await unified_ctx.send(embed=embed)
    
    async def _leaderboard_power_logic(self, unified_ctx):
        """Shared logic for total power leaderboard"""
        leaderboard_data = self._get_leaderboard_data("total_power")
        embed = self._create_leaderboard_embed(
            leaderboard_data,
            "Total Power Leaderboard", 
            "Top 10 players by combined Pokemon power (Attack + Defense + HP)"
        )
        await unified_ctx.send(embed=embed)
    
    async def _leaderboard_rarity_logic(self, unified_ctx):
        """Shared logic for rarity score leaderboard"""
        leaderboard_data = self._get_leaderboard_data("rarity_score")
        embed = self._create_leaderboard_embed(
            leaderboard_data,
            "Rarity Score Leaderboard",
            "Top 10 players by rarity score (Legendary=100pts, Mythical=150pts, Pseudo-Legendary=50pts)"
        )
        await unified_ctx.send(embed=embed)
    
    async def _leaderboard_rank_logic(self, unified_ctx, leaderboard_type: str, target_user: discord.Member):
        """Shared logic for individual rank lookup"""
        rank, score, metric = self._get_user_rank(str(target_user.id), leaderboard_type)
        embed = self._create_rank_embed(target_user, rank, score, metric, leaderboard_type)
        await unified_ctx.send(embed=embed)

    # Public methods for prefix commands
    async def leaderboard_pokemon(self, ctx):
        """Pokemon count leaderboard (prefix command)"""
        unified_ctx = create_unified_context(ctx)
        await self._leaderboard_pokemon_logic(unified_ctx)
    
    async def leaderboard_power(self, ctx):
        """Total power leaderboard (prefix command)"""
        unified_ctx = create_unified_context(ctx)
        await self._leaderboard_power_logic(unified_ctx)
    
    async def leaderboard_rarity(self, ctx):
        """Rarity score leaderboard (prefix command)"""
        unified_ctx = create_unified_context(ctx)
        await self._leaderboard_rarity_logic(unified_ctx)
    
    async def leaderboard_rank(self, ctx, leaderboard_type: str, target_user: discord.Member = None):
        """Individual rank lookup (prefix command)"""
        if target_user is None:
            target_user = ctx.author
        unified_ctx = create_unified_context(ctx)
        await self._leaderboard_rank_logic(unified_ctx, leaderboard_type, target_user)