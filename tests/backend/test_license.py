"""Tests for `/api/v1/license` (seção 6/7): plano, status e uso real."""
from tests.backend.factories import make_tenant, make_user


def test_get_license_summary_reflects_real_usage(auth_client):
    client, headers, _tenant = auth_client

    response = client.get("/api/v1/license", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["plan_code"] == "PROFESSIONAL"  # plano da fixture make_license
    assert body["current_users"] == 1  # o admin criado pela fixture
    assert body["current_vehicles"] == 0
    assert body["max_users"] is not None

    client.post("/api/v1/vehicles", headers=headers, json={"plate": "AAA1111"})
    client.post(
        "/api/v1/users", headers=headers,
        json={
            "email": "mais-um@empresa-teste.com", "full_name": "Mais Um", "password": "senhaSegura123",
            "role_code": "OPERADOR",
        },
    )

    after = client.get("/api/v1/license", headers=headers).json()
    assert after["current_vehicles"] == 1
    assert after["current_users"] == 2


def test_license_endpoint_requires_authentication(client):
    response = client.get("/api/v1/license")
    assert response.status_code == 401


def test_tenant_without_license_gets_404(client, db_session):
    tenant = make_tenant(db_session, legal_name="Empresa Sem Licença Ltda")
    make_user(db_session, tenant, email="semlicenca@empresa.com", password="Sup3rSecret!")
    db_session.commit()

    login = client.post("/api/v1/auth/login", json={"email": "semlicenca@empresa.com", "password": "Sup3rSecret!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/v1/license", headers=headers)
    assert response.status_code == 404
