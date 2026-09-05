"""Tests for `/api/v1/users` (seção 4/5): gestão de equipe, papel atribuível,
limite de plano, e as duas proteções que só existem porque isto é
autogerenciado pela própria empresa (nunca SUPER_ADMIN por aqui, nunca
autodesativação)."""
from datetime import datetime, timedelta, timezone

from app.models.enums import LicenseStatus
from app.models.license import License
from app.models.plan import Plan
from tests.backend.factories import make_tenant, make_user


def test_create_list_update_user(auth_client):
    client, headers, _tenant = auth_client

    create_response = client.post(
        "/api/v1/users", headers=headers,
        json={
            "email": "operador@empresa-teste.com", "full_name": "Operador de Teste",
            "password": "senhaSegura123", "role_code": "OPERADOR",
        },
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["role_code"] == "OPERADOR"
    assert body["status"] == "ATIVO"
    user_id = body["id"]

    list_response = client.get("/api/v1/users", headers=headers)
    assert list_response.json()["meta"]["total"] == 2  # o admin da fixture + este

    update_response = client.patch(
        f"/api/v1/users/{user_id}", headers=headers, json={"role_code": "SUPERVISOR", "status": "INATIVO"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["role_code"] == "SUPERVISOR"
    assert update_response.json()["status"] == "INATIVO"


def test_new_user_can_log_in_and_deactivated_user_cannot(auth_client, client):
    _client, headers, _tenant = auth_client
    created = client.post(
        "/api/v1/users", headers=headers,
        json={
            "email": "novo@empresa-teste.com", "full_name": "Novo Usuário",
            "password": "senhaSegura123", "role_code": "OPERADOR",
        },
    ).json()

    login = client.post("/api/v1/auth/login", json={"email": "novo@empresa-teste.com", "password": "senhaSegura123"})
    assert login.status_code == 200

    client.patch(f"/api/v1/users/{created['id']}", headers=headers, json={"status": "INATIVO"})

    blocked_login = client.post(
        "/api/v1/auth/login", json={"email": "novo@empresa-teste.com", "password": "senhaSegura123"}
    )
    assert blocked_login.status_code == 401


def test_reset_password_lets_user_log_in_with_new_password(auth_client, client):
    _client, headers, _tenant = auth_client
    created = client.post(
        "/api/v1/users", headers=headers,
        json={
            "email": "resetavel@empresa-teste.com", "full_name": "Vai Trocar Senha",
            "password": "senhaAntiga123", "role_code": "OPERADOR",
        },
    ).json()

    response = client.post(
        f"/api/v1/users/{created['id']}/reset-password", headers=headers, json={"new_password": "senhaNova456"},
    )
    assert response.status_code == 204

    old_login = client.post(
        "/api/v1/auth/login", json={"email": "resetavel@empresa-teste.com", "password": "senhaAntiga123"}
    )
    assert old_login.status_code == 401
    new_login = client.post(
        "/api/v1/auth/login", json={"email": "resetavel@empresa-teste.com", "password": "senhaNova456"}
    )
    assert new_login.status_code == 200


def test_create_user_rejects_duplicate_email(auth_client):
    client, headers, _tenant = auth_client
    payload = {
        "email": "duplicado@empresa-teste.com", "full_name": "Um", "password": "senhaSegura123", "role_code": "OPERADOR",
    }
    assert client.post("/api/v1/users", headers=headers, json=payload).status_code == 201
    second = client.post("/api/v1/users", headers=headers, json={**payload, "full_name": "Dois"})
    assert second.status_code == 409


def test_create_user_rejects_super_admin_role(auth_client):
    client, headers, _tenant = auth_client
    response = client.post(
        "/api/v1/users", headers=headers,
        json={
            "email": "naodeveria@empresa-teste.com", "full_name": "Não Deveria Existir",
            "password": "senhaSegura123", "role_code": "SUPER_ADMIN",
        },
    )
    assert response.status_code in (400, 422)


def test_user_cannot_deactivate_own_account(auth_client, db_session):
    from app.models.user import User

    client, headers, tenant = auth_client
    me = db_session.query(User).filter(User.tenant_id == tenant.id).one()

    response = client.patch(f"/api/v1/users/{me.id}", headers=headers, json={"status": "INATIVO"})
    assert response.status_code == 422


def test_user_creation_respects_plan_limit(auth_client, db_session):
    client, headers, tenant = auth_client

    starter_plan = db_session.query(Plan).filter(Plan.code == "STARTER").one()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(
        License(
            tenant_id=tenant.id, plan_id=starter_plan.id, license_key=f"user-limit-test-{tenant.id}",
            status=LicenseStatus.ACTIVE, issued_at=now + timedelta(minutes=1), expires_at=now + timedelta(days=30),
            max_users=1,
        )
    )
    db_session.commit()  # a fixture já criou 1 usuário — o limite já está no teto

    response = client.post(
        "/api/v1/users", headers=headers,
        json={
            "email": "alemdolimite@empresa-teste.com", "full_name": "Além do Limite",
            "password": "senhaSegura123", "role_code": "OPERADOR",
        },
    )
    assert response.status_code == 402
    assert response.json()["error"]["code"] == "OF-API-402"


def test_user_endpoints_require_authentication(client):
    response = client.get("/api/v1/users")
    assert response.status_code == 401


def test_operador_role_cannot_manage_users(client, db_session):
    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="operador@empresa-teste.com", password="Sup3rSecret!", role_code="OPERADOR")
    db_session.commit()
    login = client.post("/api/v1/auth/login", json={"email": "operador@empresa-teste.com", "password": "Sup3rSecret!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/api/v1/users", headers=headers,
        json={"email": "x@x.com", "full_name": "X", "password": "senhaSegura123", "role_code": "OPERADOR"},
    )
    assert response.status_code == 403


def test_tenant_a_cannot_see_user_from_tenant_b(client, db_session):
    tenant_a = make_tenant(db_session, legal_name="Empresa A Ltda")
    tenant_b = make_tenant(db_session, legal_name="Empresa B Ltda")
    make_user(db_session, tenant_a, email="usera@a.com", password="Sup3rSecret!")
    user_b = make_user(db_session, tenant_b, email="userb@b.com", password="Sup3rSecret!")
    db_session.commit()

    headers_a = {
        "Authorization": "Bearer "
        + client.post("/api/v1/auth/login", json={"email": "usera@a.com", "password": "Sup3rSecret!"}).json()["access_token"]
    }

    assert client.get(f"/api/v1/users/{user_b.id}", headers=headers_a).status_code == 404
    assert client.get("/api/v1/users", headers=headers_a).json()["meta"]["total"] == 1  # só a própria
