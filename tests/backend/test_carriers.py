"""Tests for `/api/v1/carriers` (seção 11): CRUD, validação, isolamento."""
from tests.backend.factories import make_license, make_tenant, make_user


def test_create_list_get_update_delete_carrier(auth_client):
    client, headers, _tenant = auth_client

    create_response = client.post(
        "/api/v1/carriers", headers=headers,
        json={"legal_name": "Rápido Log Ltda", "cnpj": "11.111.111/0001-11"},
    )
    assert create_response.status_code == 201
    carrier_id = create_response.json()["id"]
    assert create_response.json()["status"] == "ATIVO"

    list_response = client.get("/api/v1/carriers", headers=headers)
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["meta"]["total"] == 1
    assert body["items"][0]["legal_name"] == "Rápido Log Ltda"

    get_response = client.get(f"/api/v1/carriers/{carrier_id}", headers=headers)
    assert get_response.status_code == 200

    update_response = client.patch(
        f"/api/v1/carriers/{carrier_id}", headers=headers, json={"trade_name": "Rápido"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["trade_name"] == "Rápido"

    delete_response = client.delete(f"/api/v1/carriers/{carrier_id}", headers=headers)
    assert delete_response.status_code == 204

    after_delete = client.get("/api/v1/carriers", headers=headers)
    assert after_delete.json()["meta"]["total"] == 0  # soft delete: some da listagem


def test_create_carrier_rejects_duplicate_cnpj_within_tenant(auth_client):
    client, headers, _tenant = auth_client
    payload = {"legal_name": "Empresa X", "cnpj": "22.222.222/0001-22"}

    first = client.post("/api/v1/carriers", headers=headers, json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/carriers", headers=headers, json={**payload, "legal_name": "Empresa Y"})
    assert second.status_code == 409


def test_carrier_endpoints_require_authentication(client):
    response = client.get("/api/v1/carriers")
    assert response.status_code == 401


def test_visualizador_role_cannot_create_carrier(client, db_session):
    tenant = make_tenant(db_session)
    make_user(
        db_session, tenant, email="readonly@empresa-teste.com", password="Sup3rSecret!", role_code="VISUALIZADOR",
    )
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"email": "readonly@empresa-teste.com", "password": "Sup3rSecret!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post("/api/v1/carriers", headers=headers, json={"legal_name": "Não Deveria Criar"})
    assert response.status_code == 403


def test_tenant_a_cannot_see_or_edit_carrier_from_tenant_b(client, db_session):
    tenant_a = make_tenant(db_session, legal_name="Empresa A Ltda")
    tenant_b = make_tenant(db_session, legal_name="Empresa B Ltda")
    make_user(db_session, tenant_a, email="usera@a.com", password="Sup3rSecret!")
    make_user(db_session, tenant_b, email="userb@b.com", password="Sup3rSecret!")
    db_session.commit()

    headers_a = {
        "Authorization": "Bearer "
        + client.post("/api/v1/auth/login", json={"email": "usera@a.com", "password": "Sup3rSecret!"}).json()[
            "access_token"
        ]
    }
    headers_b = {
        "Authorization": "Bearer "
        + client.post("/api/v1/auth/login", json={"email": "userb@b.com", "password": "Sup3rSecret!"}).json()[
            "access_token"
        ]
    }

    created = client.post("/api/v1/carriers", headers=headers_b, json={"legal_name": "Transportadora B"})
    carrier_b_id = created.json()["id"]

    get_from_a = client.get(f"/api/v1/carriers/{carrier_b_id}", headers=headers_a)
    assert get_from_a.status_code == 404

    update_from_a = client.patch(
        f"/api/v1/carriers/{carrier_b_id}", headers=headers_a, json={"trade_name": "Invasão"}
    )
    assert update_from_a.status_code == 404

    list_from_a = client.get("/api/v1/carriers", headers=headers_a)
    assert list_from_a.json()["meta"]["total"] == 0
