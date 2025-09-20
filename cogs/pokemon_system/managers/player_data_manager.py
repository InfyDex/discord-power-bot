"""
Player Data Manager
Handles loading, saving, and managing player data operations.
"""

import json
import os
from typing import Dict, List, Optional
from ..models.player_model import PlayerData


class PlayerDataManager:
    """Manages player data operations"""
    
    def __init__(self, data_file: str = "pokemon_data.json", mongo_db=None):
        self.data_file = data_file
        self.players: Dict[str, PlayerData] = {}
        self.mongo_db = mongo_db
        self.load_all_player_data()
    
    def load_all_player_data(self) -> bool:
        """Load all player data from JSON file"""
        try:
            if not os.path.exists(self.data_file):
                print(f"Player data file {self.data_file} not found, starting fresh")
                return True
            
            with open(self.data_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            # Convert raw data to PlayerData objects
            self.players = {}
            for user_id, player_data in raw_data.items():
                self.players[user_id] = PlayerData(user_id, player_data, mongo_db=self.mongo_db)
            
            print(f"Loaded data for {len(self.players)} players")
            return True
            
        except json.JSONDecodeError as e:
            print(f"Error decoding {self.data_file}: {e}")
            return False
        except Exception as e:
            print(f"Error loading player data: {e}")
            return False
    
    def save_all_player_data(self) -> bool:
        """Save all player data to JSON file"""
        try:
            # Convert PlayerData objects to dictionaries
            raw_data = {}
            for user_id, player_data in self.players.items():
                raw_data[user_id] = player_data.to_dict()
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(raw_data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error saving player data: {e}")
            return False
    
    def get_player(self, user_id: str) -> PlayerData:
        """Get player data, creating new player if doesn't exist"""
        if user_id not in self.players:
            self.players[user_id] = PlayerData(user_id, mongo_db=self.mongo_db)
            self.save_all_player_data()  # Save immediately when creating new player
        
        return self.players[user_id]
    
    def player_exists(self, user_id: str) -> bool:
        """Check if player exists in the system"""
        return user_id in self.players
    
    def initialize_player(self, user_id: str) -> PlayerData:
        """Initialize a new player (alias for get_player for backward compatibility)"""
        return self.get_player(user_id)
    
    def save_player(self, user_id: str) -> bool:
        """Save specific player's data"""
        if user_id not in self.players:
            return False
        
        return self.save_all_player_data()
    
    def delete_player(self, user_id: str) -> bool:
        """Delete a player's data"""
        if user_id in self.players:
            del self.players[user_id]
            return self.save_all_player_data()
        return False
    
    def get_player_stats_summary(self) -> Dict[str, any]:
        """Get summary statistics for all players"""
        if not self.players:
            return {
                "total_players": 0,
                "total_pokemon_caught": 0,
                "total_encounters": 0,
                "average_catch_rate": 0.0
            }
        
        total_players = len(self.players)
        total_pokemon_caught = sum(len(player.pokemon_collection) for player in self.players.values())
        total_encounters = sum(player.stats.total_encounters for player in self.players.values())
        
        # Calculate average catch rate
        total_caught = sum(player.stats.total_caught for player in self.players.values())
        average_catch_rate = (total_caught / total_encounters * 100) if total_encounters > 0 else 0.0
        
        return {
            "total_players": total_players,
            "total_pokemon_caught": total_pokemon_caught,
            "total_encounters": total_encounters,
            "average_catch_rate": average_catch_rate
        }
    
    def get_leaderboard_by_catches(self, limit: int = 10) -> List[tuple]:
        """Get leaderboard sorted by total Pokemon caught"""
        player_scores = [
            (user_id, len(player.pokemon_collection)) 
            for user_id, player in self.players.items()
        ]
        
        # Sort by Pokemon count (descending)
        player_scores.sort(key=lambda x: x[1], reverse=True)
        
        return player_scores[:limit]
    
    def get_leaderboard_by_catch_rate(self, limit: int = 10) -> List[tuple]:
        """Get leaderboard sorted by catch rate (minimum 10 encounters)"""
        player_scores = []
        
        for user_id, player in self.players.items():
            if player.stats.total_encounters >= 10:  # Minimum encounters for fair comparison
                catch_rate = player.stats.get_catch_rate()
                player_scores.append((user_id, catch_rate))
        
        # Sort by catch rate (descending)
        player_scores.sort(key=lambda x: x[1], reverse=True)
        
        return player_scores[:limit]
    
    def get_rarity_distribution(self) -> Dict[str, int]:
        """Get distribution of Pokemon rarities across all players"""
        rarity_counts = {"Common": 0, "Uncommon": 0, "Rare": 0, "Legendary": 0}
        
        for player in self.players.values():
            for pokemon in player.pokemon_collection:
                if pokemon.rarity in rarity_counts:
                    rarity_counts[pokemon.rarity] += 1
        
        return rarity_counts
    
    @property
    def total_players(self) -> int:
        """Get total number of registered players"""
        return len(self.players)