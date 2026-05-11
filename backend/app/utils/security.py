"""Password hashing and verification helpers built on Argon2."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plaintext: str) -> str:
    """Hash a plaintext password for persistent storage."""

    return _hasher.hash(plaintext)


def verify_password(hashed: str, plaintext: str) -> bool:
    """Return ``True`` when ``plaintext`` matches the stored Argon2 hash."""

    try:
        return _hasher.verify(hashed, plaintext)
    except VerifyMismatchError:
        return False
