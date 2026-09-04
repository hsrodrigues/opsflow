"""Pytest fixtures for the backend test suite.

`DATABASE_URL`/`JWT_SECRET` are set **before** anything under `app` is
imported, so `app.core.config.get_settings()` (cached with `lru_cache`)
never picks up the developer's real `.env` — every test run gets its own
throwaway SQLite file.

The schema is created by running the **real** Alembic migration (not
`Base.metadata.create_all`): that's what also seeds the RBAC roles/
permissions and the plan catalog (see
`database/migrations/versions/0001_initial_schema.py`), which tests need,
and it doubles as a functional check that the migration itself still
applies cleanly — the same guarantee documented in `docs/DATABASE.md`.
"""
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./.pytest_opsflow_test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-never-used-outside-pytest")
os.environ.setdefault("APP_ENV", "development")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

_TEST_DB_PATH = Path(".pytest_opsflow_test.db")
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"


@pytest.fixture(scope="session")
def test_engine():
    """A SQLite engine pointed at a freshly migrated (schema + seed) database.

    `app.core.database` opens its own separate engine against this same
    file path (via `DATABASE_URL`, set above) — code under test that uses
    `SessionLocal`/`get_db` directly (e.g. the health check) still reads the
    tables created here. Both engines must be disposed before the file can
    be deleted on Windows, which keeps an open handle until every
    connection in a pool is closed.
    """
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()
    alembic_cfg = Config(str(_MIGRATIONS_DIR / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(f"sqlite:///{_TEST_DB_PATH}", future=True)
    yield engine
    engine.dispose()
    from app.core.database import engine as app_engine

    app_engine.dispose()
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink(missing_ok=True)


@pytest.fixture()
def db_session(test_engine):
    """A database session wrapped in a transaction that is always rolled back.

    `join_transaction_mode="create_savepoint"` is what makes this safe even
    though application code (the services under test) calls `db.commit()`
    itself: each such commit only releases/reopens a SAVEPOINT nested inside
    the outer transaction started below, which the `finally` block always
    rolls back — so no test's data ever leaks into the next one.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(
        bind=connection, future=True, expire_on_commit=False, join_transaction_mode="create_savepoint",
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    """A FastAPI TestClient with `get_db` overridden to use `db_session`."""
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
