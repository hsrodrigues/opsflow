"""Tests for `/api/v1/platform/tenants` (seção 54): console de plataforma,
exclusivo de `SUPER_ADMIN` — nunca acessível por um usuário de empresa,
não importa o papel."""
from app.models.role import Role
from app.models.user import User
from tests.backend.factories import make_tenant, make_user


def _super_admin_headers(client, db_session, *, email: str = "plataforma@opsflow.local") -> dict:
    role = db_session.query(Role).filter(Role.code == "SUPER_ADMIN").one()
    user = User(tenant_id=None, email=email, full_name="Admin Plataforma", password_hash="x")
    from app.core.security import hash_password

    user.password_hash = hash_password("Sup3rSecret!")
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Sup3rSecret!"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_super_admin_can_create_and_list_tenants(client, db_session):
    headers = _super_admin_headers(client, db_session)

    response = client.post(
        "/api/v1/platform/tenants", headers=headers,
        json={
            "legal_name": "Nova Empresa Ltda", "cnpj": "12.345.678/0001-90", "plan_code": "STARTER",
            "admin_email": "admin@novaempresa.com", "admin_full_name": "Admin da Empresa",
            "admin_password": "senhaSegura123",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["plan_code"] == "STARTER"
    assert body["license_status"] == "TRIAL"
    assert body["user_count"] == 1
    # Sem override: max_users/max_vehicles (resolvidos) refletem o plano,
    # mas o _override (bruto) precisa ser None — é essa distinção que
    # permite à tela de editar licença saber que "3" aqui é só herdado do
    # plano, não um valor customizado que trocar de plano preservaria.
    assert body["max_users_override"] is None
    assert body["max_vehicles_override"] is None
    assert body["max_users"] == 3  # limite padrão do STARTER

    listing = client.get("/api/v1/platform/tenants", headers=headers)
    assert listing.status_code == 200
    names = {t["legal_name"] for t in listing.json()}
    assert "Nova Empresa Ltda" in names


def test_admin_created_by_platform_can_log_in(client, db_session):
    headers = _super_admin_headers(client, db_session)
    client.post(
        "/api/v1/platform/tenants", headers=headers,
        json={
            "legal_name": "Empresa Onboarding Ltda", "admin_email": "dono@onboarding.com",
            "admin_full_name": "Dono", "admin_password": "senhaSegura123",
        },
    )

    login = client.post("/api/v1/auth/login", json={"email": "dono@onboarding.com", "password": "senhaSegura123"})
    assert login.status_code == 200
    assert login.json()["user"]["roles"] == ["ADMIN_EMPRESA"]


def test_create_tenant_rejects_duplicate_cnpj(client, db_session):
    headers = _super_admin_headers(client, db_session)
    payload = {
        "legal_name": "Empresa Um Ltda", "cnpj": "11.111.111/0001-11", "admin_email": "um@empresa.com",
        "admin_full_name": "Um", "admin_password": "senhaSegura123",
    }
    assert client.post("/api/v1/platform/tenants", headers=headers, json=payload).status_code == 201

    duplicate = {**payload, "legal_name": "Empresa Dois Ltda", "admin_email": "dois@empresa.com"}
    response = client.post("/api/v1/platform/tenants", headers=headers, json=duplicate)
    assert response.status_code == 409


def test_update_tenant_license_changes_plan_and_status(client, db_session):
    headers = _super_admin_headers(client, db_session)
    created = client.post(
        "/api/v1/platform/tenants", headers=headers,
        json={
            "legal_name": "Empresa Para Upgrade Ltda", "admin_email": "upgrade@empresa.com",
            "admin_full_name": "Admin", "admin_password": "senhaSegura123",
        },
    ).json()

    response = client.patch(
        f"/api/v1/platform/tenants/{created['id']}/license", headers=headers,
        json={"plan_code": "BUSINESS", "status": "ACTIVE", "max_vehicles": 2000},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plan_code"] == "BUSINESS"
    assert body["license_status"] == "ACTIVE"
    assert body["max_vehicles"] == 2000
    assert body["max_vehicles_override"] == 2000  # override de verdade, não herdado do plano
    assert body["max_users_override"] is None  # este continua sem override nenhum


def test_update_tenant_license_can_explicitly_clear_an_override(client, db_session):
    """Bug real reportado pelo usuário: mudar o status pra ACTIVE não tirava
    a data de expiração antiga, porque o service tratava "campo mandado como
    null" igual a "campo não mandado" — nunca dava pra limpar nada. `max_
    vehicles` sofre do mesmo jeito (não dava pra voltar a usar o limite do
    plano depois de um override)."""
    headers = _super_admin_headers(client, db_session)
    created = client.post(
        "/api/v1/platform/tenants", headers=headers,
        json={
            "legal_name": "Empresa Limpar Override Ltda", "admin_email": "clear@empresa.com",
            "admin_full_name": "Admin", "admin_password": "senhaSegura123",
        },
    ).json()
    client.patch(
        f"/api/v1/platform/tenants/{created['id']}/license", headers=headers,
        json={"expires_at": "2027-01-01T00:00:00", "max_vehicles": 999},
    )

    response = client.patch(
        f"/api/v1/platform/tenants/{created['id']}/license", headers=headers,
        json={"status": "ACTIVE", "expires_at": None, "max_vehicles": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["license_status"] == "ACTIVE"
    assert body["license_expires_at"] is None
    assert body["max_vehicles"] == 100  # volta ao limite do plano STARTER (default do onboarding)


def test_update_tenant_license_without_a_field_leaves_it_unchanged(client, db_session):
    """O contraste com o teste acima: um campo que nem aparece no JSON
    precisa continuar intocado — só `null` explícito limpa."""
    headers = _super_admin_headers(client, db_session)
    created = client.post(
        "/api/v1/platform/tenants", headers=headers,
        json={
            "legal_name": "Empresa Campo Intocado Ltda", "admin_email": "untouched@empresa.com",
            "admin_full_name": "Admin", "admin_password": "senhaSegura123",
        },
    ).json()
    client.patch(
        f"/api/v1/platform/tenants/{created['id']}/license", headers=headers,
        json={"expires_at": "2027-06-15T00:00:00"},
    )

    response = client.patch(
        f"/api/v1/platform/tenants/{created['id']}/license", headers=headers, json={"status": "ACTIVE"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["license_status"] == "ACTIVE"
    assert body["license_expires_at"].startswith("2027-06-15")


def test_deactivate_tenant_blocks_its_users_from_logging_in(client, db_session):
    headers = _super_admin_headers(client, db_session)
    created = client.post(
        "/api/v1/platform/tenants", headers=headers,
        json={
            "legal_name": "Empresa Vai Ser Desativada Ltda", "admin_email": "desativada@empresa.com",
            "admin_full_name": "Admin", "admin_password": "senhaSegura123",
        },
    ).json()

    deactivate = client.patch(
        f"/api/v1/platform/tenants/{created['id']}", headers=headers, json={"is_active": False},
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    login = client.post(
        "/api/v1/auth/login", json={"email": "desativada@empresa.com", "password": "senhaSegura123"}
    )
    assert login.status_code == 403


def test_regular_tenant_user_cannot_access_platform_endpoints(auth_client):
    client, headers, _tenant = auth_client
    assert client.get("/api/v1/platform/tenants", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/platform/tenants", headers=headers,
        json={
            "legal_name": "Não Deveria Existir", "admin_email": "x@x.com", "admin_full_name": "X",
            "admin_password": "senhaSegura123",
        },
    ).status_code == 403


def test_operador_role_cannot_access_platform_endpoints_either(client, db_session):
    """Confirma que o bloqueio é por `tenant_id is None`, não por permissão —
    nenhum papel de empresa (nem o mais restrito) chega perto disto."""
    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="operador@empresa-teste.com", password="Sup3rSecret!", role_code="OPERADOR")
    db_session.commit()
    login = client.post("/api/v1/auth/login", json={"email": "operador@empresa-teste.com", "password": "Sup3rSecret!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/platform/tenants", headers=headers).status_code == 403


def test_platform_endpoints_require_authentication(client):
    response = client.get("/api/v1/platform/tenants")
    assert response.status_code == 401
