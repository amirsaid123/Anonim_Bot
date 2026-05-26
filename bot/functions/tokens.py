import secrets
import string

# Opaque, cryptographically-random tokens used in anonymous-message links.
# Same alphabet/length is reused for any future "custom" tokens picked by
# premium users — the custom path will validate the length/charset matches.

_ALPHABET = string.ascii_letters + string.digits  # base62
_DEFAULT_LENGTH = 8


def generate_token(length: int = _DEFAULT_LENGTH) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
