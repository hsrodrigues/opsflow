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
# Um scheduler de verdade rodando em thread própria, batendo no banco de
# teste no timer dele, deixaria a suíte flaky — os jobs são testados
# chamando `run()` diretamente (ver test_jobs.py), nunca via APScheduler.
os.environ.setdefault("JOBS_ENABLED", "false")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

_TEST_DB_PATH = Path(".pytest_opsflow_test.db")
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"

# Semeadas uma única vez pela migration (roles/permissions/plans) — nunca
# apagadas entre testes, só os dados que cada teste cria.
_SEED_TABLES = {"roles", "permissions", "role_permissions", "plans", "alembic_version"}


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
    """A plain database session, cleaned up by deleting every non-seed row
    after the test (not by rolling back a transaction).

    An earlier version of this fixture wrapped each test in an outer
    transaction (`connection.begin()` + `join_transaction_mode=
    "create_savepoint"`) and rolled it back on teardown — the standard
    SQLAlchemy testing recipe. In this project that rollback silently failed
    to undo `app.services.*`'s own `db.commit()` calls when a request went
    through `TestClient` (FastAPI's sync endpoints run in a worker thread,
    which apparently broke the savepoint nesting): rows from one test kept
    existing in the next one. It went unnoticed until a fixture reused a
    fixed e-mail across tests and hit a UNIQUE-constraint collision — see
    the git history of this file if the symptom resurfaces. Explicit
    row-deletion has none of that ambiguity: it isn't relying on any
    session/thread affinity to work.
    """
    from app.models import Base

    session_factory = sessionmaker(bind=test_engine, future=True, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        with test_engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                if table.name not in _SEED_TABLES:
                    connection.execute(table.delete())


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


@pytest.fixture()
def auth_client(client, db_session):
    """A `(client, headers, tenant, user)` tuple, already logged in as an
    ADMIN_EMPRESA of a fresh tenant — the setup every cadastros CRUD test needs.
    """
    from tests.backend.factories import make_license, make_tenant, make_user

    tenant = make_tenant(db_session)
    make_license(db_session, tenant)
    make_user(db_session, tenant, email="admin@auth-client-fixture.com", password="Sup3rSecret!")
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login", json={"email": "admin@auth-client-fixture.com", "password": "Sup3rSecret!"}
    )
    assert response.status_code == 200, response.text
    access_token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    return client, headers, tenant
