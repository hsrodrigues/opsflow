"""Tests for the self-activation flow (seção 6): `SUPER_ADMIN` gera uma
`license_key` solta (`POST /api/v1/platform/license-keys`), e um prospect
sem conta nenhuma a resgata (`POST /api/v1/activation/activate`, sem
autenticação — o único endpoint da API assim de propósito)."""
from app.models.license import License
from app.models.role import Role
from app.models.user import User


def _super_admin_headers(client, db_session, *, email: str = "plataforma@opsflow.local") -> dict:
    from app.core.security import hash_password

    role = db_session.query(Role).filter(Role.code == "SUPER_ADMIN").one()
    user = User(tenant_id=None, email=email, full_name="Admin Plataforma", password_hash=hash_password("Sup3rSecret!"))
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Sup3rSecret!"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _generate_key(client, headers, **overrides) -> dict:
    payload = {"plan_code": "STARTER", "trial_days": 30, **overrides}
    response = client.post("/api/v1/platform/license-keys", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_generate_license_key_has_no_tenant_yet(client, db_session):
    headers = _super_admin_headers(client, db_session)
    key = _generate_key(client, headers, plan_code="PROFESSIONAL", trial_days=14)
    assert key["tenant_id"] is None
    assert key["tenant_name"] is None
    assert key["activated_at"] is None
    assert key["plan_code"] == "PROFESSIONAL"
    assert key["pending_trial_days"] == 14


def test_list_license_keys_includes_generated_key(client, db_session):
    headers = _super_admin_headers(client, db_session)
    key = _generate_key(client, headers)

    response = client.get("/api/v1/platform/license-keys", headers=headers)
    assert response.status_code == 200
    assert any(k["license_key"] == key["license_key"] for k in response.json())


def test_activation_creates_tenant_and_logs_in_automatically(client, db_session):
    headers = _super_admin_headers(client, db_session)
    key = _generate_key(client, headers, plan_code="PROFESSIONAL", trial_days=14)

    response = client.post(
        "/api/v1/activation/activate",
        json={
            "license_key": key["license_key"], "legal_name": "Empresa Ativada Ltda",
            "admin_full_name": "Dono", "admin_email": "dono@ativada.com", "admin_password": "senhaSegura123",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "dono@ativada.com"
    assert body["user"]["roles"] == ["ADMIN_EMPRESA"]
    assert body["access_token"]
    assert body["license"]["plan_code"] == "PROFESSIONAL"
    assert body["license"]["status"] == "TRIAL"

    license_row = db_session.query(License).filter(License.license_key == key["license_key"]).one()
    assert license_row.tenant_id is not None
    assert license_row.activated_at is not None
    assert license_row.expires_at is not None


def test_activation_requires_no_authentication(client, db_session):
    """O ponto inteiro do endpoint: funciona sem NENHUM header de
    Authorization — o prospect não tem conta nenhuma ainda."""
    headers = _super_admin_headers(client, db_session)
    key = _generate_key(client, headers)

    response = client.post(
        "/api/v1/activation/activate",
        json={
            "license_key": key["license_key"], "legal_name": "Sem Auth Ltda",
            "admin_full_name": "X", "admin_email": "semauth@empresa.com", "admin_password": "senhaSegura123",
        },
    )
    assert response.status_code == 200


def test_cannot_reuse_an_already_activated_key(client, db_session):
    headers = _super_admin_headers(client, db_session)
    key = _generate_key(client, headers)
    first_payload = {
        "license_key": key["license_key"], "legal_name": "Primeira Ativação Ltda",
        "admin_full_name": "X", "admin_email": "primeiro@empresa.com", "admin_password": "senhaSegura123",
    }
    assert client.post("/api/v1/activation/activate", json=first_payload).status_code == 200

    second_payload = {**first_payload, "legal_name": "Segunda Tentativa Ltda", "admin_email": "segundo@empresa.com"}
    response = client.post("/api/v1/activation/activate", json=second_payload)
    assert response.status_code == 409


def test_activation_rejects_unknown_key(client):
    response = client.post(
        "/api/v1/activation/activate",
        json={
            "license_key": "chave-inexistente", "legal_name": "X", "admin_full_name": "X",
            "admin_email": "x@x.com", "admin_password": "senhaSegura123",
        },
    )
    assert response.status_code == 422


def test_activation_rejects_duplicate_email(client, db_session):
    headers = _super_admin_headers(client, db_session)
    key1 = _generate_key(client, headers)
    key2 = _generate_key(client, headers)

    payload = {
        "license_key": key1["license_key"], "legal_name": "Primeira Ltda", "admin_full_name": "X",
        "admin_email": "repetido@empresa.com", "admin_password": "senhaSegura123",
    }
    assert client.post("/api/v1/activation/activate", json=payload).status_code == 200

    second = {**payload, "license_key": key2["license_key"], "legal_name": "Segunda Ltda"}
    response = client.post("/api/v1/activation/activate", json=second)
    assert response.status_code == 409


def test_regular_tenant_user_cannot_generate_license_keys(auth_client):
    client, headers, _tenant = auth_client
    response = client.post("/api/v1/platform/license-keys", headers=headers, json={"plan_code": "STARTER"})
    assert response.status_code == 403


def test_license_key_endpoints_require_authentication(client):
    assert client.get("/api/v1/platform/license-keys").status_code == 401
    assert client.post("/api/v1/platform/license-keys", json={"plan_code": "STARTER"}).status_code == 401
