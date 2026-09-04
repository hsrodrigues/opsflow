"""Password hashing (seção 6/24: "Criptografia — Argon2 ou bcrypt").

Centralized here so both the seed script and the Fase 2 authentication
service hash/verify passwords the exact same way. Uses Argon2id via
`argon2-cffi`, the OWASP-recommended default for new applications.
"""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password for storage. Never log the input or output."""
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored hash. Never raises on mismatch."""
    try:
        return _hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    """Whether a stored hash uses outdated Argon2 parameters and should be re-hashed on next login."""
    return _hasher.check_needs_rehash(password_hash)
