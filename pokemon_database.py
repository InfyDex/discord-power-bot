"""
Pokemon Database for the Legion Discord Bot
Contains comprehensive Pokemon data including stats, types, descriptions, and images.
"""

POKEMON_DATABASE = {
    # Generation 1 - Kanto Pokemon
    1: {
        "name": "Bulbasaur",
        "types": ["Grass", "Poison"],
        "rarity": "Uncommon",
        "catch_rate": 0.55,
        "generation": 1,
        "description": "A strange seed was planted on its back at birth. The plant sprouts and grows with this Pokémon.",
        "stats": {
            "hp": 45,
            "attack": 49,
            "defense": 49,
            "sp_attack": 65,
            "sp_defense": 65,
            "speed": 45,
            "total": 318
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/1.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png"
    },
    2: {
        "name": "Ivysaur",
        "types": ["Grass", "Poison"],
        "rarity": "Rare",
        "catch_rate": 0.35,
        "generation": 1,
        "description": "When the bulb on its back grows large, it appears to lose the ability to stand on its hind legs.",
        "stats": {
            "hp": 60,
            "attack": 62,
            "defense": 63,
            "sp_attack": 80,
            "sp_defense": 80,
            "speed": 60,
            "total": 405
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/2.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/2.png"
    },
    3: {
        "name": "Venusaur",
        "types": ["Grass", "Poison"],
        "rarity": "Legendary",
        "catch_rate": 0.15,
        "generation": 1,
        "description": "The plant blooms when it is absorbing solar energy. It stays on the move to seek sunlight.",
        "stats": {
            "hp": 80,
            "attack": 82,
            "defense": 83,
            "sp_attack": 100,
            "sp_defense": 100,
            "speed": 80,
            "total": 525
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/3.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/3.png"
    },
    4: {
        "name": "Charmander",
        "types": ["Fire"],
        "rarity": "Uncommon",
        "catch_rate": 0.55,
        "generation": 1,
        "description": "Obviously prefers hot places. When it rains, steam is said to spout from the tip of its tail.",
        "stats": {
            "hp": 39,
            "attack": 52,
            "defense": 43,
            "sp_attack": 60,
            "sp_defense": 50,
            "speed": 65,
            "total": 309
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/4.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/4.png"
    },
    5: {
        "name": "Charmeleon",
        "types": ["Fire"],
        "rarity": "Rare",
        "catch_rate": 0.35,
        "generation": 1,
        "description": "When it swings its burning tail, it elevates the temperature to unbearably hot levels.",
        "stats": {
            "hp": 58,
            "attack": 64,
            "defense": 58,
            "sp_attack": 80,
            "sp_defense": 65,
            "speed": 80,
            "total": 405
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/5.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/5.png"
    },
    6: {
        "name": "Charizard",
        "types": ["Fire", "Flying"],
        "rarity": "Legendary",
        "catch_rate": 0.15,
        "generation": 1,
        "description": "Spits fire that is hot enough to melt boulders. Known to cause forest fires unintentionally.",
        "stats": {
            "hp": 78,
            "attack": 84,
            "defense": 78,
            "sp_attack": 109,
            "sp_defense": 85,
            "speed": 100,
            "total": 534
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/6.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/6.png"
    },
    7: {
        "name": "Squirtle",
        "types": ["Water"],
        "rarity": "Uncommon",
        "catch_rate": 0.55,
        "generation": 1,
        "description": "After birth, its back swells and hardens into a shell. Powerfully sprays foam from its mouth.",
        "stats": {
            "hp": 44,
            "attack": 48,
            "defense": 65,
            "sp_attack": 50,
            "sp_defense": 64,
            "speed": 43,
            "total": 314
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/7.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/7.png"
    },
    8: {
        "name": "Wartortle",
        "types": ["Water"],
        "rarity": "Rare",
        "catch_rate": 0.35,
        "generation": 1,
        "description": "Often hides in water to stalk unwary prey. For swimming fast, it moves its ears to maintain balance.",
        "stats": {
            "hp": 59,
            "attack": 63,
            "defense": 80,
            "sp_attack": 65,
            "sp_defense": 80,
            "speed": 58,
            "total": 405
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/8.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/8.png"
    },
    9: {
        "name": "Blastoise",
        "types": ["Water"],
        "rarity": "Legendary",
        "catch_rate": 0.15,
        "generation": 1,
        "description": "A brutal Pokémon with pressurized water jets on its shell. They are used for high speed tackles.",
        "stats": {
            "hp": 79,
            "attack": 83,
            "defense": 100,
            "sp_attack": 85,
            "sp_defense": 105,
            "speed": 78,
            "total": 530
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/9.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/9.png"
    },
    10: {
        "name": "Caterpie",
        "types": ["Bug"],
        "rarity": "Common",
        "catch_rate": 0.85,
        "generation": 1,
        "description": "Its short feet are tipped with suction pads that enable it to tirelessly climb slopes and walls.",
        "stats": {
            "hp": 45,
            "attack": 30,
            "defense": 35,
            "sp_attack": 20,
            "sp_defense": 20,
            "speed": 45,
            "total": 195
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/10.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/10.png"
    },
    11: {
        "name": "Metapod",
        "types": ["Bug"],
        "rarity": "Common",
        "catch_rate": 0.75,
        "generation": 1,
        "description": "This Pokémon is vulnerable to attack while its shell is soft, exposing its weak and tender body.",
        "stats": {
            "hp": 50,
            "attack": 20,
            "defense": 55,
            "sp_attack": 25,
            "sp_defense": 25,
            "speed": 30,
            "total": 205
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/11.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/11.png"
    },
    12: {
        "name": "Butterfree",
        "types": ["Bug", "Flying"],
        "rarity": "Uncommon",
        "catch_rate": 0.45,
        "generation": 1,
        "description": "In battle, it flaps its wings at high speed to release highly toxic dust into the air.",
        "stats": {
            "hp": 60,
            "attack": 45,
            "defense": 50,
            "sp_attack": 90,
            "sp_defense": 80,
            "speed": 70,
            "total": 395
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/12.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/12.png"
    },
    13: {
        "name": "Weedle",
        "types": ["Bug", "Poison"],
        "rarity": "Common",
        "catch_rate": 0.85,
        "generation": 1,
        "description": "Often found in forests, eating leaves. It has a sharp venomous stinger on its head.",
        "stats": {
            "hp": 40,
            "attack": 35,
            "defense": 30,
            "sp_attack": 20,
            "sp_defense": 20,
            "speed": 50,
            "total": 195
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/13.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/13.png"
    },
    14: {
        "name": "Kakuna",
        "types": ["Bug", "Poison"],
        "rarity": "Common",
        "catch_rate": 0.75,
        "generation": 1,
        "description": "Almost incapable of moving, this Pokémon can only harden its shell to protect itself from predators.",
        "stats": {
            "hp": 45,
            "attack": 25,
            "defense": 50,
            "sp_attack": 25,
            "sp_defense": 25,
            "speed": 35,
            "total": 205
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/14.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/14.png"
    },
    15: {
        "name": "Beedrill",
        "types": ["Bug", "Poison"],
        "rarity": "Uncommon",
        "catch_rate": 0.45,
        "generation": 1,
        "description": "Flies at high speed and attacks using its large venomous stingers on its forelegs and tail.",
        "stats": {
            "hp": 65,
            "attack": 90,
            "defense": 40,
            "sp_attack": 45,
            "sp_defense": 80,
            "speed": 75,
            "total": 395
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/15.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/15.png"
    },
    16: {
        "name": "Pidgey",
        "types": ["Normal", "Flying"],
        "rarity": "Common",
        "catch_rate": 0.85,
        "generation": 1,
        "description": "A common sight in forests and woods. It flaps its wings at ground level to kick up blinding sand.",
        "stats": {
            "hp": 40,
            "attack": 45,
            "defense": 40,
            "sp_attack": 35,
            "sp_defense": 35,
            "speed": 56,
            "total": 251
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/16.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/16.png"
    },
    17: {
        "name": "Pidgeotto",
        "types": ["Normal", "Flying"],
        "rarity": "Uncommon",
        "catch_rate": 0.45,
        "generation": 1,
        "description": "Very protective of its sprawling territorial area, this Pokémon will fiercely peck at any intruder.",
        "stats": {
            "hp": 63,
            "attack": 60,
            "defense": 55,
            "sp_attack": 50,
            "sp_defense": 50,
            "speed": 71,
            "total": 349
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/17.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/17.png"
    },
    18: {
        "name": "Pidgeot",
        "types": ["Normal", "Flying"],
        "rarity": "Rare",
        "catch_rate": 0.25,
        "generation": 1,
        "description": "When hunting, it skims the surface of water at high speed to pick off unwary prey such as Magikarp.",
        "stats": {
            "hp": 83,
            "attack": 80,
            "defense": 75,
            "sp_attack": 70,
            "sp_defense": 70,
            "speed": 101,
            "total": 479
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/18.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/18.png"
    },
    19: {
        "name": "Rattata",
        "types": ["Normal"],
        "rarity": "Common",
        "catch_rate": 0.85,
        "generation": 1,
        "description": "Bites anything when it attacks. Small and very quick, it is a common sight in many places.",
        "stats": {
            "hp": 30,
            "attack": 56,
            "defense": 35,
            "sp_attack": 25,
            "sp_defense": 35,
            "speed": 72,
            "total": 253
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/19.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/19.png"
    },
    20: {
        "name": "Raticate",
        "types": ["Normal"],
        "rarity": "Uncommon",
        "catch_rate": 0.45,
        "generation": 1,
        "description": "It uses its whiskers to maintain its balance. It apparently slows down if they are cut off.",
        "stats": {
            "hp": 55,
            "attack": 81,
            "defense": 60,
            "sp_attack": 50,
            "sp_defense": 70,
            "speed": 97,
            "total": 413
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/20.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/20.png"
    },
    25: {
        "name": "Pikachu",
        "types": ["Electric"],
        "rarity": "Uncommon",
        "catch_rate": 0.60,
        "generation": 1,
        "description": "When several of these Pokémon gather, their electricity could build and cause lightning storms.",
        "stats": {
            "hp": 35,
            "attack": 55,
            "defense": 40,
            "sp_attack": 50,
            "sp_defense": 50,
            "speed": 90,
            "total": 320
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png"
    },
    26: {
        "name": "Raichu",
        "types": ["Electric"],
        "rarity": "Rare",
        "catch_rate": 0.25,
        "generation": 1,
        "description": "Its long tail serves as a ground to protect itself from its own high voltage power.",
        "stats": {
            "hp": 60,
            "attack": 90,
            "defense": 55,
            "sp_attack": 90,
            "sp_defense": 80,
            "speed": 110,
            "total": 485
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/26.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/26.png"
    },
    129: {
        "name": "Magikarp",
        "types": ["Water"],
        "rarity": "Common",
        "catch_rate": 0.95,
        "generation": 1,
        "description": "In the distant past, it was somewhat stronger than the horribly weak descendants that exist today.",
        "stats": {
            "hp": 20,
            "attack": 10,
            "defense": 55,
            "sp_attack": 15,
            "sp_defense": 20,
            "speed": 80,
            "total": 200
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/129.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/129.png"
    },
    130: {
        "name": "Gyarados",
        "types": ["Water", "Flying"],
        "rarity": "Legendary",
        "catch_rate": 0.10,
        "generation": 1,
        "description": "Rarely seen in the wild. Huge and vicious, it is capable of destroying entire cities in a rage.",
        "stats": {
            "hp": 95,
            "attack": 125,
            "defense": 79,
            "sp_attack": 60,
            "sp_defense": 100,
            "speed": 81,
            "total": 540
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/130.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/130.png"
    },
    131: {
        "name": "Lapras",
        "types": ["Water", "Ice"],
        "rarity": "Rare",
        "catch_rate": 0.20,
        "generation": 1,
        "description": "A Pokémon that has been overhunted almost to extinction. It can ferry people across bodies of water.",
        "stats": {
            "hp": 130,
            "attack": 85,
            "defense": 80,
            "sp_attack": 85,
            "sp_defense": 95,
            "speed": 60,
            "total": 535
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/131.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/131.png"
    },
    133: {
        "name": "Eevee",
        "types": ["Normal"],
        "rarity": "Uncommon",
        "catch_rate": 0.40,
        "generation": 1,
        "description": "Its genetic code is irregular. It may mutate if it is exposed to radiation from element stones.",
        "stats": {
            "hp": 55,
            "attack": 55,
            "defense": 50,
            "sp_attack": 45,
            "sp_defense": 65,
            "speed": 55,
            "total": 325
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/133.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/133.png"
    },
    143: {
        "name": "Snorlax",
        "types": ["Normal"],
        "rarity": "Rare",
        "catch_rate": 0.25,
        "generation": 1,
        "description": "Very lazy. Just eats and sleeps. As its rotund bulk builds, it becomes steadily more slothful.",
        "stats": {
            "hp": 160,
            "attack": 110,
            "defense": 65,
            "sp_attack": 65,
            "sp_defense": 110,
            "speed": 30,
            "total": 540
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/143.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/143.png"
    },
    144: {
        "name": "Articuno",
        "types": ["Ice", "Flying"],
        "rarity": "Legendary",
        "catch_rate": 0.05,
        "generation": 1,
        "description": "A legendary bird Pokémon that is said to appear to doomed people who are lost in icy mountains.",
        "stats": {
            "hp": 90,
            "attack": 85,
            "defense": 100,
            "sp_attack": 95,
            "sp_defense": 125,
            "speed": 85,
            "total": 580
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/144.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/144.png"
    },
    145: {
        "name": "Zapdos",
        "types": ["Electric", "Flying"],
        "rarity": "Legendary",
        "catch_rate": 0.05,
        "generation": 1,
        "description": "A legendary bird Pokémon that is said to appear from clouds while dropping enormous lightning bolts.",
        "stats": {
            "hp": 90,
            "attack": 90,
            "defense": 85,
            "sp_attack": 125,
            "sp_defense": 90,
            "speed": 100,
            "total": 580
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/145.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/145.png"
    },
    146: {
        "name": "Moltres",
        "types": ["Fire", "Flying"],
        "rarity": "Legendary",
        "catch_rate": 0.05,
        "generation": 1,
        "description": "Known as the legendary bird of fire. Every flap of its wings creates a dazzling flash of flames.",
        "stats": {
            "hp": 90,
            "attack": 100,
            "defense": 90,
            "sp_attack": 125,
            "sp_defense": 85,
            "speed": 90,
            "total": 580
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/146.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/146.png"
    },
    147: {
        "name": "Dratini",
        "types": ["Dragon"],
        "rarity": "Rare",
        "catch_rate": 0.30,
        "generation": 1,
        "description": "Long considered a mythical Pokémon until recently when a small colony was found living underwater.",
        "stats": {
            "hp": 41,
            "attack": 64,
            "defense": 45,
            "sp_attack": 50,
            "sp_defense": 50,
            "speed": 50,
            "total": 300
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/147.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/147.png"
    },
    148: {
        "name": "Dragonair",
        "types": ["Dragon"],
        "rarity": "Rare",
        "catch_rate": 0.20,
        "generation": 1,
        "description": "A mystical Pokémon that exudes a gentle aura. Has the ability to change climate conditions.",
        "stats": {
            "hp": 61,
            "attack": 84,
            "defense": 65,
            "sp_attack": 70,
            "sp_defense": 70,
            "speed": 70,
            "total": 420
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/148.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/148.png"
    },
    149: {
        "name": "Dragonite",
        "types": ["Dragon", "Flying"],
        "rarity": "Legendary",
        "catch_rate": 0.10,
        "generation": 1,
        "description": "An extremely rarely seen marine Pokémon. Its intelligence is said to match that of humans.",
        "stats": {
            "hp": 91,
            "attack": 134,
            "defense": 95,
            "sp_attack": 100,
            "sp_defense": 100,
            "speed": 80,
            "total": 600
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/149.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/149.png"
    },
    150: {
        "name": "Mewtwo",
        "types": ["Psychic"],
        "rarity": "Legendary",
        "catch_rate": 0.03,
        "generation": 1,
        "description": "It was created by a scientist after years of horrific gene splicing and DNA engineering experiments.",
        "stats": {
            "hp": 106,
            "attack": 110,
            "defense": 90,
            "sp_attack": 154,
            "sp_defense": 90,
            "speed": 130,
            "total": 680
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/150.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/150.png"
    },
    151: {
        "name": "Mew",
        "types": ["Psychic"],
        "rarity": "Legendary",
        "catch_rate": 0.01,
        "generation": 1,
        "description": "So rare that it is still said to be a mirage by many experts. Only a few people have seen it worldwide.",
        "stats": {
            "hp": 100,
            "attack": 100,
            "defense": 100,
            "sp_attack": 100,
            "sp_defense": 100,
            "speed": 100,
            "total": 600
        },
        "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/151.png",
        "sprite_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/151.png"
    }
}

# Rarity distribution weights
RARITY_WEIGHTS = {
    "Common": 0.50,      # 50%
    "Uncommon": 0.30,    # 30%
    "Rare": 0.15,        # 15%
    "Legendary": 0.05    # 5%
}

# Type color mapping for embeds
TYPE_COLORS = {
    "Normal": 0xA8A878,
    "Fire": 0xF08030,
    "Water": 0x6890F0,
    "Electric": 0xF8D030,
    "Grass": 0x78C850,
    "Ice": 0x98D8D8,
    "Fighting": 0xC03028,
    "Poison": 0xA040A0,
    "Ground": 0xE0C068,
    "Flying": 0xA890F0,
    "Psychic": 0xF85888,
    "Bug": 0xA8B820,
    "Rock": 0xB8A038,
    "Ghost": 0x705898,
    "Dragon": 0x7038F8,
    "Dark": 0x705848,
    "Steel": 0xB8B8D0,
    "Fairy": 0xEE99AC
}

def get_pokemon_by_rarity(rarity):
    """Get all Pokemon of a specific rarity"""
    return [pokemon for pokemon in POKEMON_DATABASE.values() if pokemon['rarity'] == rarity]

def get_random_pokemon_by_rarity():
    """Get a random Pokemon based on rarity weights"""
    import random
    
    rand = random.random()
    cumulative = 0
    
    for rarity, weight in RARITY_WEIGHTS.items():
        cumulative += weight
        if rand <= cumulative:
            pokemon_list = get_pokemon_by_rarity(rarity)
            if pokemon_list:
                return random.choice(pokemon_list)
    
    # Fallback to common
    return random.choice(get_pokemon_by_rarity("Common"))

def get_pokemon_by_id(pokemon_id):
    """Get Pokemon by its ID"""
    return POKEMON_DATABASE.get(pokemon_id)

def get_pokemon_by_name(name):
    """Get Pokemon by its name"""
    for pokemon in POKEMON_DATABASE.values():
        if pokemon['name'].lower() == name.lower():
            return pokemon
    return None

def get_type_color(pokemon_types):
    """Get the color for a Pokemon based on its primary type"""
    primary_type = pokemon_types[0] if pokemon_types else "Normal"
    return TYPE_COLORS.get(primary_type, 0x000000)