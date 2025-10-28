"""
Update Pokemon data from PokeAPI to fix incorrect information.
This script fetches correct data from PokeAPI and updates the JSON file
while preserving all Pokemon entries.
"""

import requests
import json
import os
import time
import shutil
from datetime import datetime
from typing import Dict, Any, Optional

# Configuration
API_BASE = "https://pokeapi.co/api/v2/pokemon/"
SPECIES_API_BASE = "https://pokeapi.co/api/v2/pokemon-species/"
RATE_LIMIT_DELAY = 1.0  # seconds between API calls
MAX_RETRIES = 3
TIMEOUT = 10

def log_message(level: str, message: str):
    """Log messages with timestamp and level"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")

def safe_api_request(url: str, retries: int = MAX_RETRIES) -> Optional[Dict[str, Any]]:
    """Make a safe API request with retries and rate limiting"""
    for attempt in range(retries):
        try:
            log_message("DEBUG", f"API Request: {url} (attempt {attempt + 1}/{retries})")
            response = requests.get(url, timeout=TIMEOUT)
            
            if response.status_code == 200:
                log_message("DEBUG", f"✅ Success: {url}")
                return response.json()
            elif response.status_code == 404:
                log_message("WARN", f"❌ Not found: {url}")
                return None
            else:
                log_message("WARN", f"⚠️ HTTP {response.status_code}: {url}")
                
        except requests.exceptions.Timeout:
            log_message("WARN", f"⏰ Timeout for {url}")
        except requests.exceptions.RequestException as e:
            log_message("WARN", f"🌐 Network error for {url}: {e}")
        
        if attempt < retries - 1:
            log_message("INFO", f"🔄 Retrying in {RATE_LIMIT_DELAY} seconds...")
            time.sleep(RATE_LIMIT_DELAY)
    
    log_message("ERROR", f"❌ Failed to fetch after {retries} attempts: {url}")
    return None

def get_pokemon_data_from_api(pokemon_id: int) -> Optional[Dict[str, Any]]:
    """Fetch Pokemon data from PokeAPI"""
    log_message("INFO", f"🔍 Fetching data for Pokemon ID {pokemon_id}")
    
    # Fetch main Pokemon data
    pokemon_url = f"{API_BASE}{pokemon_id}"
    pokemon_data = safe_api_request(pokemon_url)
    
    if not pokemon_data:
        return None
    
    # Fetch species data for description and generation
    species_url = f"{SPECIES_API_BASE}{pokemon_id}"
    species_data = safe_api_request(species_url)
    
    # Add delay between API calls
    time.sleep(RATE_LIMIT_DELAY)
    
    return {
        "pokemon": pokemon_data,
        "species": species_data
    }

def extract_english_description(flavor_texts: list) -> str:
    """Extract English description from flavor text entries"""
    if not flavor_texts:
        return f"A mysterious Pokemon."
    
    # Look for English descriptions, prefer newer games
    english_texts = [
        entry for entry in flavor_texts 
        if entry.get("language", {}).get("name") == "en"
    ]
    
    if not english_texts:
        return f"A mysterious Pokemon."
    
    # Prefer descriptions from newer games (they're usually better)
    preferred_versions = ["sword", "shield", "ultra-sun", "ultra-moon", "sun", "moon"]
    
    for version in preferred_versions:
        for entry in english_texts:
            if entry.get("version", {}).get("name") == version:
                description = entry.get("text", "").replace("\n", " ").replace("\f", " ")
                return " ".join(description.split())  # Clean up whitespace
    
    # If no preferred version found, use the first English description
    description = english_texts[0].get("text", "").replace("\n", " ").replace("\f", " ")
    return " ".join(description.split())

def normalize_pokemon_name(name: str) -> str:
    """Normalize Pokemon name for consistency"""
    # Replace hyphens with spaces and title case
    return name.replace("-", " ").title()

def determine_rarity(is_legendary: bool, is_mythical: bool, base_total: int) -> str:
    """Determine Pokemon rarity based on its characteristics"""
    if is_legendary or is_mythical:
        return "Legendary"
    elif base_total >= 600:  # Pseudo-legendary threshold
        return "Rare"
    elif base_total >= 500:
        return "Uncommon"
    else:
        return "Common"

def calculate_catch_rate(base_catch_rate: int, is_legendary: bool, is_mythical: bool) -> float:
    """Calculate catch rate as a probability (0.0 to 1.0)"""
    if is_legendary or is_mythical:
        return 0.05  # Very low catch rate for legendaries
    
    # Convert from PokeAPI's 0-255 scale to 0.0-1.0 probability
    # Formula: roughly base_catch_rate / 255, but adjusted for game balance
    if base_catch_rate >= 200:
        return 0.7  # Common Pokemon
    elif base_catch_rate >= 120:
        return 0.5  # Uncommon Pokemon
    elif base_catch_rate >= 75:
        return 0.4  # Rare Pokemon
    elif base_catch_rate >= 45:
        return 0.3  # Very rare Pokemon
    else:
        return 0.15  # Ultra rare non-legendary Pokemon

def update_pokemon_entry(pokemon_id: str, current_data: Dict[str, Any], api_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update a Pokemon entry with correct data from PokeAPI"""
    pokemon_data = api_data["pokemon"]
    species_data = api_data.get("species")
    
    log_message("INFO", f"📝 Updating Pokemon ID {pokemon_id}")
    
    # Extract correct information
    correct_name = normalize_pokemon_name(pokemon_data["name"])
    correct_types = [type_info["type"]["name"].title() for type_info in pokemon_data["types"]]
    
    # Stats
    stats = {}
    for stat in pokemon_data["stats"]:
        stat_name = stat["stat"]["name"].replace("-", "_")
        if stat_name == "special_attack":
            stat_name = "sp_attack"
        elif stat_name == "special_defense":
            stat_name = "sp_defense"
        stats[stat_name] = stat["base_stat"]
    
    stats["total"] = sum(stats.values())
    
    # Generation and rarity from species data
    if species_data:
        generation = species_data["generation"]["url"].split("/")[-2]
        correct_generation = int(generation)
        
        is_legendary = species_data.get("is_legendary", False)
        is_mythical = species_data.get("is_mythical", False)
        base_catch_rate = species_data.get("capture_rate", 45)
        
        # Get proper description
        flavor_texts = species_data.get("flavor_text_entries", [])
        correct_description = extract_english_description(flavor_texts)
    else:
        # Fallback if species data not available
        log_message("WARN", f"⚠️ No species data for ID {pokemon_id}, using fallbacks")
        correct_generation = current_data.get("generation", 1)
        is_legendary = False
        is_mythical = False
        base_catch_rate = 45
        correct_description = f"A {correct_types[0].lower()} type Pokemon."
    
    correct_rarity = determine_rarity(is_legendary, is_mythical, stats["total"])
    correct_catch_rate = calculate_catch_rate(base_catch_rate, is_legendary, is_mythical)
    
    # Image URLs
    correct_image_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{pokemon_id}.png"
    correct_sprite_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pokemon_id}.png"
    
    # Create updated entry
    updated_data = current_data.copy()
    
    # Track what we're updating
    updates = []
    
    if updated_data.get("name") != correct_name:
        updates.append(f"name: '{updated_data.get('name')}' → '{correct_name}'")
        updated_data["name"] = correct_name
    
    if updated_data.get("types") != correct_types:
        updates.append(f"types: {updated_data.get('types')} → {correct_types}")
        updated_data["types"] = correct_types
    
    if updated_data.get("generation") != correct_generation:
        updates.append(f"generation: {updated_data.get('generation')} → {correct_generation}")
        updated_data["generation"] = correct_generation
    
    if updated_data.get("rarity") != correct_rarity:
        updates.append(f"rarity: '{updated_data.get('rarity')}' → '{correct_rarity}'")
        updated_data["rarity"] = correct_rarity
    
    if abs(updated_data.get("catch_rate", 0) - correct_catch_rate) > 0.01:
        updates.append(f"catch_rate: {updated_data.get('catch_rate')} → {correct_catch_rate}")
        updated_data["catch_rate"] = correct_catch_rate
    
    # Always update description to get proper one instead of generic
    old_desc = updated_data.get("description", "")
    if old_desc != correct_description:
        if "A " in old_desc and " Pokemon from Generation " in old_desc:
            updates.append(f"description: Generic → Proper PokeAPI description")
        else:
            updates.append(f"description: Updated to accurate PokeAPI description")
        updated_data["description"] = correct_description
    
    # Update stats if different
    current_stats = updated_data.get("stats", {})
    if current_stats != stats:
        old_total = current_stats.get("total", 0)
        updates.append(f"stats total: {old_total} → {stats['total']}")
        updated_data["stats"] = stats
    
    # Update image URLs if different
    if updated_data.get("image_url") != correct_image_url:
        updates.append(f"image_url: Updated to correct URL")
        updated_data["image_url"] = correct_image_url
    
    if updated_data.get("sprite_url") != correct_sprite_url:
        updates.append(f"sprite_url: Updated to correct URL")
        updated_data["sprite_url"] = correct_sprite_url
    
    if updates:
        log_message("INFO", f"✅ Updated {correct_name} (ID {pokemon_id}):")
        for update in updates[:3]:  # Show first 3 updates
            log_message("INFO", f"   • {update}")
        if len(updates) > 3:
            log_message("INFO", f"   • ... and {len(updates) - 3} more updates")
    else:
        log_message("INFO", f"✅ {correct_name} (ID {pokemon_id}) - No updates needed")
    
    return updated_data

def update_pokemon_data():
    """Main function to update Pokemon data from PokeAPI"""
    json_path = os.path.join(os.path.dirname(__file__), "..", "pokemon_master_database.json")
    
    if not os.path.exists(json_path):
        log_message("ERROR", f"❌ Pokemon database file not found at {json_path}")
        return False
    
    log_message("INFO", "🚀 Starting Pokemon data update from PokeAPI")
    log_message("INFO", "=" * 60)
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{json_path}.backup_before_pokeapi_update_{timestamp}"
    shutil.copy2(json_path, backup_path)
    log_message("INFO", f"📁 Created backup: {backup_path}")
    
    try:
        # Load current data
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        log_message("INFO", f"📋 Loaded {len(data)} Pokemon from JSON")
        
        # Process ALL Pokemon to check and fix any incorrect data
        pokemon_ids = sorted([int(pid) for pid in data.keys()])
        total_pokemon = len(pokemon_ids)
        
        log_message("INFO", f"🎯 Processing ALL {total_pokemon} Pokemon to validate every field")
        log_message("INFO", f"⏱️ Estimated time: ~{total_pokemon * RATE_LIMIT_DELAY / 60:.1f} minutes")
        log_message("INFO", f"💡 This will ensure ALL data is correct, not just duplicates")
        
        updated_count = 0
        error_count = 0
        no_update_count = 0
        
        start_time = time.time()
        
        # Process ALL Pokemon
        for i, pokemon_id in enumerate(pokemon_ids, 1):
            pokemon_id_str = str(pokemon_id)
            
            if pokemon_id_str not in data:
                log_message("WARN", f"⚠️ Pokemon ID {pokemon_id} not found in data")
                continue
            
            try:
                log_message("INFO", f"📊 Progress: {i}/{total_pokemon} - Processing Pokemon ID {pokemon_id}")
                
                api_data = get_pokemon_data_from_api(pokemon_id)
                if api_data:
                    old_data = data[pokemon_id_str].copy()
                    data[pokemon_id_str] = update_pokemon_entry(pokemon_id_str, data[pokemon_id_str], api_data)
                    
                    # Check if anything was actually updated
                    if old_data != data[pokemon_id_str]:
                        updated_count += 1
                    else:
                        no_update_count += 1
                else:
                    log_message("ERROR", f"❌ Failed to fetch data for ID {pokemon_id}")
                    error_count += 1
                
            except Exception as e:
                log_message("ERROR", f"❌ Error updating Pokemon ID {pokemon_id}: {e}")
                error_count += 1
            
            # Progress updates every 50 Pokemon
            if i % 50 == 0:
                elapsed = time.time() - start_time
                avg_time_per_pokemon = elapsed / i
                remaining = (total_pokemon - i) * avg_time_per_pokemon
                
                log_message("INFO", f"📊 Progress Summary:")
                log_message("INFO", f"   ✅ Updated: {updated_count}")
                log_message("INFO", f"   ⚠️ No changes: {no_update_count}")
                log_message("INFO", f"   ❌ Errors: {error_count}")
                log_message("INFO", f"   ⏱️ Remaining: ~{remaining/60:.1f} minutes")
                
                # Save progress periodically
                log_message("INFO", f"💾 Saving progress...")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
        
        total_time = time.time() - start_time
        log_message("INFO", f"\n⏱️ Total processing time: {total_time/60:.1f} minutes")
        
        # Save the current progress
        log_message("INFO", f"\n💾 Saving progress...")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Final summary
        log_message("INFO", f"\n" + "=" * 60)
        log_message("INFO", f"🎉 POKEMON DATA VALIDATION COMPLETE!")
        log_message("INFO", f"=" * 60)
        log_message("INFO", f"📊 Final Results:")
        log_message("INFO", f"   ✅ Pokemon updated: {updated_count}")
        log_message("INFO", f"   ⚠️ No changes needed: {no_update_count}")
        log_message("INFO", f"   ❌ Errors encountered: {error_count}")
        log_message("INFO", f"   📄 Updated file: {json_path}")
        log_message("INFO", f"   📁 Backup saved: {backup_path}")
        
        # Verify duplicates are resolved
        log_message("INFO", f"\n🧪 Verifying duplicate resolution...")
        name_counts = {}
        for pokemon_data in data.values():
            name = pokemon_data.get("name", "")
            name_counts[name] = name_counts.get(name, 0) + 1
        
        remaining_duplicates = {name: count for name, count in name_counts.items() if count > 1}
        
        if remaining_duplicates:
            log_message("WARN", f"⚠️ Still have {len(remaining_duplicates)} duplicate names:")
            for name, count in remaining_duplicates.items():
                log_message("WARN", f"   '{name}': {count} times")
        else:
            log_message("INFO", f"✅ All duplicate names resolved!")
        
        # Validate data completeness
        log_message("INFO", f"\n🔍 Data Quality Check:")
        missing_fields = 0
        for pokemon_id, pokemon_data in data.items():
            required_fields = ["name", "types", "rarity", "generation", "description", "stats", "catch_rate", "image_url", "sprite_url"]
            for field in required_fields:
                if field not in pokemon_data or pokemon_data[field] is None:
                    log_message("WARN", f"   Missing {field} in Pokemon ID {pokemon_id}")
                    missing_fields += 1
        
        if missing_fields == 0:
            log_message("INFO", f"✅ All required fields present for all Pokemon!")
        else:
            log_message("WARN", f"⚠️ Found {missing_fields} missing fields")
        
        log_message("INFO", f"📊 Final Pokemon count: {len(data)} (should be 1025)")
        
        if len(data) == 1025:
            log_message("INFO", f"✅ Pokemon count is correct!")
        else:
            log_message("WARN", f"⚠️ Pokemon count mismatch! Expected 1025, got {len(data)}")
        
        return True
    
    except Exception as e:
        log_message("ERROR", f"❌ Error during update: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    
    log_message("INFO", "Pokemon Data Updater from PokeAPI")
    log_message("INFO", "This will fetch correct data and fix issues without deleting Pokemon")
    
    success = update_pokemon_data()
    
    if success:
        log_message("INFO", f"\n🎉 Pokemon data update completed!")
        log_message("INFO", f"💡 You can now:")
        log_message("INFO", f"   1. Check git diff to see what changed")
        log_message("INFO", f"   2. Run migration: py scripts/migrate_master_pokemon_to_mongo.py")
    else:
        log_message("ERROR", f"\n❌ Update failed. Check the errors above.")
