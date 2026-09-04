"""Session-related models: refresh tokens and password-reset tokens.

Not explicitly named in the seção 8 table list, but required to implement
the flows the spec does require (seção 5: refresh token, "controle de
sessões", "recuperação de senha"). Only a salted hash of each token is ever
stored — never the raw token — so a database leak alone cannot be used to
impersonate a session.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.types import bigint_pk


class RefreshToken(Base):
    """A single refresh-token session, enabling rotation and revocation."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<RefreshToken id={self.id} user_id={self.user_id}>"


class PasswordResetToken(Base):
    """A single-use token issued for the "esqueci minha senha" flow."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<PasswordResetToken id={self.id} user_id={self.user_id}>"
