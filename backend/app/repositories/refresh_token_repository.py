"""Refresh token repository — not tenant-scoped (see `session.py`: a token
belongs to a `user_id`; the user's tenant is reached indirectly).
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_token
from app.models.session import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self, *, user_id: int, raw_token: str, issued_at: datetime, expires_at: datetime,
        ip_address: str | None, user_agent: str | None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            issued_at=issued_at,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(token)
        self.db.flush()
        return token

    def get_active_by_raw_token(self, raw_token: str) -> RefreshToken | None:
        """Return the token row iff it exists, is not revoked and is not expired."""
        token_hash = hash_token(raw_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        token = self.db.execute(stmt).scalar_one_or_none()
        if token is None or token.revoked_at is not None:
            return None
        if token.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
            return None
        return token

    def revoke(self, token: RefreshToken) -> None:
        token.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.flush()
