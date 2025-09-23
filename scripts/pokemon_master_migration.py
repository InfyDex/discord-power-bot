import os
import json

from dotenv import load_dotenv
from pymongo import MongoClient, errors

load_dotenv()
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
db_name = os.getenv("MONGO_DB_NAME", "legion_discord_bot")
client = MongoClient(mongo_uri)
db = client[db_name]
pokemons = db["pokemons"]

# ensure index for fast lookups
pokemons.create_index("id", unique=True)
pokemons.create_index("types")
pokemons.create_index("name")

# Load and parse the JSON file
json_path = os.path.join(os.path.dirname(__file__), "..", "pokemon_master_database.json")
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

inserted = 0
skipped = 0
for str_id, poke in data.items():
    poke_doc = poke.copy()
    poke_doc["id"] = int(str_id)
    try:
        pokemons.insert_one(poke_doc)
        inserted += 1
    except errors.DuplicateKeyError:
        skipped += 1
    except Exception as e:
        print(f"Error inserting Pokémon {poke_doc['name']} (ID {str_id}): {e}")

print(f"Migration complete. Inserted: {inserted}, Skipped (duplicates): {skipped}")

# Verification step
count = pokemons.count_documents({})
print(f"Total Pokémon documents in collection: {count}")

# Check a few sample Pokémon by ID
sample_ids = [1, 2, 3]
for sid in sample_ids:
    doc = pokemons.find_one({"id": sid})
    if doc:
        print(f"Verified: ID {sid} - Name: {doc['name']}")
    else:
        print(f"Missing: ID {sid}")
