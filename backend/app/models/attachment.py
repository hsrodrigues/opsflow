"""Attachment model — files uploaded against an occurrence (seção 14)."""
from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin
from app.models.types import bigint_pk


class Attachment(Base, TimestampMixin, TenantMixin):
    """A file uploaded against an occurrence (the only attachable entity in the MVP)."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=True)
    occurrence_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("occurrences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)

    occurrence: Mapped["Occurrence"] = relationship(back_populates="attachments")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Attachment id={self.id} file_name={self.file_name!r}>"
