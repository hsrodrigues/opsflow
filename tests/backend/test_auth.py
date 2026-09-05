"""Tests for the authentication flow (seção 5): login, refresh, logout."""
from app.core.config import get_settings
from tests.backend.factories import make_license, make_tenant, make_user


def test_login_with_valid_credentials_returns_tokens_and_user_info(client, db_session):
    tenant = make_tenant(db_session)
    make_license(db_session, tenant)
    make_user(db_session, tenant, email="admin@empresa-teste.com", password="Sup3rSecret!")
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login", json={"email": "admin@empresa-teste.com", "password": "Sup3rSecret!"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["email"] == "admin@empresa-teste.com"
    assert "ADMIN_EMPRESA" in body["user"]["roles"]
    assert body["license"]["status"] == "ACTIVE"


def test_login_license_info_falls_back_to_plan_limits_when_license_has_no_override(client, db_session):
    tenant = make_tenant(db_session)
    make_license(db_session, tenant)  # não define max_users/max_vehicles -> deve herdar do plano PROFESSIONAL
    make_user(db_session, tenant, email="planlimits@empresa-teste.com", password="Sup3rSecret!")
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login", json={"email": "planlimits@empresa-teste.com", "password": "Sup3rSecret!"}
    )

    license_info = response.json()["license"]
    assert license_info["max_users"] == 10  # limite do plano PROFESSIONAL (seção 7)
    assert license_info["max_vehicles"] == 500


def test_login_with_wrong_password_is_rejected(client, db_session):
    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="user@empresa-teste.com", password="Sup3rSecret!")
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login", json={"email": "user@empresa-teste.com", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "OF-API-401"


def test_login_with_unknown_email_returns_generic_error(client, db_session):
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@nowhere.com", "password": "whatever123"}
    )

    assert response.status_code == 401


def test_account_locks_after_max_failed_attempts(client, db_session):
    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="lockout@empresa-teste.com", password="Sup3rSecret!")
    db_session.commit()
    max_attempts = get_settings().max_login_attempts

    for _ in range(max_attempts):
        client.post(
            "/api/v1/auth/login", json={"email": "lockout@empresa-teste.com", "password": "wrong-password"}
        )

    # mesmo com a senha CORRETA, a conta deve estar bloqueada agora
    response = client.post(
        "/api/v1/auth/login", json={"email": "lockout@empresa-teste.com", "password": "Sup3rSecret!"}
    )
    assert response.status_code == 401
    assert "bloqueada" in response.json()["error"]["message"].lower()


def test_refresh_rotates_the_token_and_invalidates_the_old_one(client, db_session):
    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="refresh@empresa-teste.com", password="Sup3rSecret!")
    db_session.commit()
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "refresh@empresa-teste.com", "password": "Sup3rSecret!"}
    )
    old_refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh_token})
    assert refresh_response.status_code == 200
    assert refresh_response.json()["refresh_token"] != old_refresh_token

    reuse_response = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh_token})
    assert reuse_response.status_code == 401


def test_logout_revokes_the_refresh_token(client, db_session):
    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="logout@empresa-teste.com", password="Sup3rSecret!")
    db_session.commit()
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "logout@empresa-teste.com", "password": "Sup3rSecret!"}
    )
    refresh_token = login_response.json()["refresh_token"]

    logout_response = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_response.status_code == 204

    refresh_after_logout = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_after_logout.status_code == 401


def test_me_endpoint_requires_a_valid_bearer_token(client, db_session):
    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="me@empresa-teste.com", password="Sup3rSecret!")
    db_session.commit()
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "me@empresa-teste.com", "password": "Sup3rSecret!"}
    )
    access_token = login_response.json()["access_token"]

    unauthenticated = client.get("/api/v1/auth/me")
    assert unauthenticated.status_code == 401

    authenticated = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert authenticated.status_code == 200
    assert authenticated.json()["email"] == "me@empresa-teste.com"


def test_login_includes_the_real_company_name(client, db_session):
    """A barra de status do desktop mostrava só "Empresa #{id}" — nunca o
    nome de verdade da empresa, porque a resposta de login nunca o incluía
    (bug real reportado pelo usuário)."""
    tenant = make_tenant(db_session, legal_name="Transportes Horizonte Ltda")
    make_user(db_session, tenant, email="nome@empresa-teste.com", password="Sup3rSecret!")
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login", json={"email": "nome@empresa-teste.com", "password": "Sup3rSecret!"}
    )
    assert response.json()["user"]["tenant_name"] == "Transportes Horizonte Ltda"


def test_super_admin_has_no_tenant_name(client, db_session):
    from app.core.security import hash_password
    from app.models.role import Role
    from app.models.user import User

    role = db_session.query(Role).filter(Role.code == "SUPER_ADMIN").one()
    user = User(tenant_id=None, email="plataforma-teste@opsflow.local", full_name="X", password_hash=hash_password("Sup3rSecret!"))
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login", json={"email": "plataforma-teste@opsflow.local", "password": "Sup3rSecret!"}
    )
    assert response.json()["user"]["tenant_name"] is None


def test_any_role_can_update_own_profile_without_users_manage_permission(client, db_session):
    """Seção 26 (Configurações): editar o próprio nome/telefone é
    self-service pra qualquer papel — inclusive VISUALIZADOR, que não tem a
    permissão `users.manage` exigida por `PATCH /users/{id}` (essa segue
    exclusiva do admin, sobre QUALQUER usuário; esta aqui só sobre si mesmo)."""
    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="viewer@empresa-teste.com", password="Sup3rSecret!", role_code="VISUALIZADOR")
    db_session.commit()
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "viewer@empresa-teste.com", "password": "Sup3rSecret!"}
    )
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    response = client.patch(
        "/api/v1/auth/me", headers=headers, json={"full_name": "Novo Nome", "phone": "(11) 91234-5678"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Novo Nome"
    assert body["phone"] == "(11) 91234-5678"

    confirm = client.get("/api/v1/auth/me", headers=headers)
    assert confirm.json()["full_name"] == "Novo Nome"


def test_update_own_profile_requires_authentication(client):
    response = client.patch("/api/v1/auth/me", json={"full_name": "X"})
    assert response.status_code == 401


def test_update_own_profile_rejects_empty_name(client, db_session):
    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="emptyname@empresa-teste.com", password="Sup3rSecret!")
    db_session.commit()
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "emptyname@empresa-teste.com", "password": "Sup3rSecret!"}
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.patch("/api/v1/auth/me", headers=headers, json={"full_name": ""})
    assert response.status_code == 422
