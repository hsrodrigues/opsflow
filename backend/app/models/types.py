"""Shared column-type helpers for ORM models.

`enum_column` centralizes how Python `str` enums (see `app/models/enums.py`)
are mapped to database columns: stored as `VARCHAR` rather than a native
MySQL `ENUM` type. This keeps the same migration portable across MySQL
(production) and SQLite (fast unit tests, see `tests/backend/conftest.py`),
and avoids the schema-migration pain of native `ENUM` types whenever a new
status value is added — a new value never requires an `ALTER TABLE`.
"""
from typing import TypeVar

from sqlalchemy import BigInteger, Integer
from sqlalchemy import Enum as SAEnum

E = TypeVar("E")


def enum_column(enum_cls: type[E], *, length: int = 30) -> SAEnum:
    """Build a portable, string-backed SQLAlchemy column type for `enum_cls`."""
    return SAEnum(
        enum_cls,
        name=f"{enum_cls.__name__.lower()}_enum",
        values_callable=lambda cls: [member.value for member in cls],
        native_enum=False,
        length=length,
    )


def bigint_pk() -> BigInteger:
    """Build the column type for every auto-incrementing primary key.

    `BIGINT` on MySQL (production — headroom for high-volume tables like
    `audit_logs`/`status_history` as the platform scales past thousands of
    tenants), but `INTEGER` on SQLite: SQLite only auto-generates rowids for
    a column declared exactly `INTEGER PRIMARY KEY` — any other type
    affinity, `BIGINT` included, disables that and breaks autoincrement.
    SQLite is only ever used for fast local/unit testing (see
    `tests/backend/conftest.py`), never for production data, so this variant
    never affects real deployments.
    """
    return BigInteger().with_variant(Integer, "sqlite")
