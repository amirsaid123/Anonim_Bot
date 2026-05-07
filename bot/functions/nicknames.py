import random

_ADJECTIVES = [
    "Silent", "Hidden", "Secret", "Brave", "Clever", "Curious", "Swift",
    "Gentle", "Wild", "Dark", "Golden", "Silver", "Azure", "Crimson",
    "Mystic", "Shadow", "Storm", "Cosmic", "Lunar", "Solar", "Neon",
    "Frozen", "Blazing", "Thunder", "Whisper", "Ancient", "Phantom",
    "Mighty", "Humble", "Fierce", "Graceful", "Daring", "Lone",
    "Wandering", "Restless", "Radiant", "Velvet", "Iron", "Crystal",
]

_ANIMALS = [
    "Fox", "Wolf", "Eagle", "Tiger", "Panda", "Lion", "Bear",
    "Hawk", "Owl", "Deer", "Lynx", "Raven", "Falcon", "Jaguar",
    "Cobra", "Dragon", "Phoenix", "Unicorn", "Panther", "Cheetah",
    "Otter", "Penguin", "Dolphin", "Whale", "Octopus", "Viper",
    "Stallion", "Sparrow", "Mantis", "Gecko", "Lynx", "Moose",
    "Badger", "Ferret", "Kestrel", "Marmot", "Ibis", "Condor",
]

_EMOJI: dict[str, str] = {
    "Fox": "🦊", "Wolf": "🐺", "Eagle": "🦅", "Tiger": "🐯",
    "Panda": "🐼", "Lion": "🦁", "Bear": "🐻", "Hawk": "🦅",
    "Owl": "🦉", "Deer": "🦌", "Lynx": "🐱", "Raven": "🐦",
    "Falcon": "🦅", "Jaguar": "🐆", "Cobra": "🐍", "Dragon": "🐉",
    "Phoenix": "🔥", "Unicorn": "🦄", "Panther": "🐈", "Cheetah": "🐆",
    "Otter": "🦦", "Penguin": "🐧", "Dolphin": "🐬", "Whale": "🐋",
    "Octopus": "🐙", "Viper": "🐍", "Stallion": "🐴", "Sparrow": "🐦",
    "Mantis": "🦗", "Gecko": "🦎", "Moose": "🫎", "Badger": "🦡",
    "Ferret": "🐾", "Kestrel": "🦅", "Marmot": "🐿", "Ibis": "🦢",
    "Condor": "🦅",
}


def generate_nickname() -> str:
    adj = random.choice(_ADJECTIVES)
    animal = random.choice(_ANIMALS)
    emoji = _EMOJI.get(animal, "👤")
    return f"{emoji} {adj} {animal}"
