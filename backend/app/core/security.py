"""Password hashing and token utilities (seção 5/6/24).

Centralized here so the seed script, the auth service and future callers
hash/verify passwords and tokens the exact same way. Passwords use Argon2id
via `argon2-cffi` (OWASP-recommended default for new applications). Access
tokens are JWTs (short-lived, seção 5); refresh tokens are high-entropy
random strings — never JWTs — only ever stored as a SHA-256 hash (see
`app/models/session.py`), the same "never store the raw secret" principle
applied to passwords.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

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


# --- JWT access tokens ---

TokenType = Literal["access"]


def create_access_token(*, user_id: int, tenant_id: int | None) -> tuple[str, datetime]:
    """Issue a short-lived JWT access token. Returns (token, expires_at).

    Deliberately carries only identity (`sub`, `tenant_id`) — never roles or
    permissions. Because the token is short-lived (default 15 min) but a
    revoked role should still take effect immediately, `get_current_user`
    (Fase 2, `app/api/deps.py`) re-reads the user's roles from the database
    on every request instead of trusting a claim that could be stale.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "type": "access",
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access token. Raises `jwt.PyJWTError` on any failure."""
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Token não é um access token.")
    return payload


# --- Opaque refresh tokens ---


def generate_refresh_token() -> str:
    """Generate a new high-entropy refresh token (never a JWT — see module docstring)."""
    return secrets.token_urlsafe(48)


def hash_token(raw_token: str) -> str:
    """Hash an opaque token (refresh/password-reset) for storage.

    SHA-256, not Argon2: unlike a user-chosen password, these tokens already
    have ~256 bits of entropy from `secrets.token_urlsafe`, so a slow KDF
    buys nothing against brute force and would only add needless latency.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
