"""Tests for the backup/restore endpoints (seção 41 "Automações",
`/api/v1/platform/backups`). O suite roda contra SQLite (`conftest.py`), então
os testes de HTTP aqui usam mocks pro `backup_service` (que fala com MySQL de
verdade via `mysqldump`/`mysql`) — a prova real contra um MySQL de verdade,
criando e restaurando um backup de fato, foi feita à parte com um script
manual (não faz sentido rodar `mysqldump` num banco de testes SQLite
descartável). Aqui o que importa testar automaticamente é o que NÃO depende
de MySQL: quem pode chamar o quê, e a validação de nome de arquivo que
protege `restore_backup` de um path arbitrário."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.exceptions import ValidationFailedError
from app.services import backup_service
from app.services.backup_service import parse_backup_timestamp, restore_backup
from tests.backend.factories import make_tenant, make_user


def _super_admin_headers(client, db_session, *, email: str = "plataforma@opsflow.local") -> dict:
    from app.core.security import hash_password
    from app.models.role import Role
    from app.models.user import User

    role = db_session.query(Role).filter(Role.code == "SUPER_ADMIN").one()
    user = User(tenant_id=None, email=email, full_name="Admin Plataforma", password_hash=hash_password("Sup3rSecret!"))
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Sup3rSecret!"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_parse_backup_timestamp_reads_the_moment_from_the_filename():
    parsed = parse_backup_timestamp("opsflow_backup_20260905_143000.sql")
    assert parsed == datetime(2026, 9, 5, 14, 30, 0, tzinfo=timezone.utc)


def test_restore_backup_rejects_a_filename_outside_the_expected_pattern():
    """A validação de nome é o que impede um `filename` como
    `"../../etc/passwd"` de virar leitura arbitrária de arquivo — tem que
    rodar mesmo sem MySQL disponível, então testada direto contra o serviço,
    antes de qualquer subprocess ser disparado."""
    with pytest.raises(ValidationFailedError):
        restore_backup("../../etc/passwd")
    with pytest.raises(ValidationFailedError):
        restore_backup("nao_e_um_backup.sql")


def test_backup_endpoints_require_platform_admin(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(
        backup_service, "create_backup", lambda: tmp_path / "opsflow_backup_20260101_000000.sql",
    )
    (tmp_path / "opsflow_backup_20260101_000000.sql").write_text("-- fake dump")
    monkeypatch.setattr(backup_service, "list_backups", lambda: [])
    monkeypatch.setattr(backup_service, "restore_backup", lambda filename: None)

    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="regular@empresa-teste.com", password="Sup3rSecret!")
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"email": "regular@empresa-teste.com", "password": "Sup3rSecret!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/platform/backups").status_code == 401
    assert client.get("/api/v1/platform/backups", headers=headers).status_code == 403
    assert client.post("/api/v1/platform/backups", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/platform/backups/restore", headers=headers, json={"filename": "x.sql"}
    ).status_code == 403


def test_super_admin_can_list_create_and_restore_backups(client, db_session, monkeypatch, tmp_path):
    fake_file = tmp_path / "opsflow_backup_20260101_120000.sql"
    fake_file.write_text("-- fake dump content")

    monkeypatch.setattr(backup_service, "create_backup", lambda: fake_file)
    monkeypatch.setattr(backup_service, "list_backups", lambda: [fake_file])
    restore_calls = []
    monkeypatch.setattr(backup_service, "restore_backup", lambda filename: restore_calls.append(filename))

    headers = _super_admin_headers(client, db_session)

    create_response = client.post("/api/v1/platform/backups", headers=headers)
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["filename"] == "opsflow_backup_20260101_120000.sql"
    assert body["size_bytes"] > 0

    list_response = client.get("/api/v1/platform/backups", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()[0]["filename"] == "opsflow_backup_20260101_120000.sql"

    restore_response = client.post(
        "/api/v1/platform/backups/restore", headers=headers,
        json={"filename": "opsflow_backup_20260101_120000.sql"},
    )
    assert restore_response.status_code == 204
    assert restore_calls == ["opsflow_backup_20260101_120000.sql"]
