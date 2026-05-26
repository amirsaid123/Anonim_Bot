import hashlib

# Stable, deterministic anonymous handles per (sender, receiver) pair.
# Same sender to same receiver always sees the same handle; different
# receivers see a different handle for the same sender, so a sender's
# real identity stays hidden across conversations.

_ADJECTIVES = (
    "Curious", "Silent", "Witty", "Bold", "Gentle", "Cheery", "Sly", "Calm",
    "Daring", "Mellow", "Lucky", "Snappy", "Sunny", "Brave", "Quiet", "Quirky",
    "Mighty", "Swift", "Crafty", "Cosmic", "Velvet", "Golden", "Misty", "Plucky",
    "Stoic", "Zesty", "Frosty", "Breezy", "Mythic", "Noble", "Jolly", "Loyal",
)

_ANIMALS = (
    "Falcon", "Otter", "Panda", "Tiger", "Fox", "Owl", "Wolf", "Hare",
    "Crane", "Lynx", "Heron", "Raven", "Bear", "Stag", "Moth", "Koi",
    "Squid", "Beetle", "Mantis", "Sparrow", "Marten", "Magpie", "Bison", "Mole",
    "Newt", "Lemur", "Salmon", "Toad", "Cobra", "Yak", "Gecko", "Penguin",
)

_NUMBER_RANGE = 1000  # gives "#000" to "#999"

_SALT = b"anonim-bot/v1/nickname"


def make_nickname(sender_id: int, receiver_id: int) -> str:
    """Deterministic anonymous display handle for one (sender, receiver) pair.

    Returns something like "Curious Falcon #842". The same pair always maps to
    the same string, but the mapping is keyed on both ids — so the same sender
    looks different to different receivers.
    """
    digest = hashlib.sha256(
        _SALT + b"|" + str(sender_id).encode() + b"|" + str(receiver_id).encode()
    ).digest()
    a = int.from_bytes(digest[0:4], "big") % len(_ADJECTIVES)
    b = int.from_bytes(digest[4:8], "big") % len(_ANIMALS)
    n = int.from_bytes(digest[8:12], "big") % _NUMBER_RANGE
    return f"{_ADJECTIVES[a]} {_ANIMALS[b]} #{n:03d}"
