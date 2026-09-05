"""Tests for `/api/v1/products` — catálogo usado pela Programação pra tirar
a ambiguidade de `quantity` sem unidade declarada."""
from tests.backend.factories import make_tenant, make_user


def test_create_list_get_update_delete_product(auth_client):
    client, headers, _tenant = auth_client

    create_response = client.post(
        "/api/v1/products", headers=headers,
        json={"name": "Cimento CP-II", "sku": "CIM-50", "unit_of_measure": "KG", "default_weight_kg": 50},
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["unit_of_measure"] == "KG"
    assert body["status"] == "ATIVO"
    product_id = body["id"]

    list_response = client.get("/api/v1/products", headers=headers)
    assert list_response.json()["meta"]["total"] == 1

    get_response = client.get(f"/api/v1/products/{product_id}", headers=headers)
    assert get_response.status_code == 200

    update_response = client.patch(
        f"/api/v1/products/{product_id}", headers=headers, json={"unit_of_measure": "TONELADA"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["unit_of_measure"] == "TONELADA"

    delete_response = client.delete(f"/api/v1/products/{product_id}", headers=headers)
    assert delete_response.status_code == 204
    assert client.get("/api/v1/products", headers=headers).json()["meta"]["total"] == 0


def test_product_defaults_to_unidade_when_unit_not_given(auth_client):
    client, headers, _tenant = auth_client
    response = client.post("/api/v1/products", headers=headers, json={"name": "Item genérico"})
    assert response.status_code == 201
    assert response.json()["unit_of_measure"] == "UNIDADE"


def test_search_products_by_name(auth_client):
    client, headers, _tenant = auth_client
    client.post("/api/v1/products", headers=headers, json={"name": "Grãos a granel", "unit_of_measure": "TONELADA"})
    client.post("/api/v1/products", headers=headers, json={"name": "Peças eletrônicas", "unit_of_measure": "CAIXA"})

    response = client.get("/api/v1/products?q=grãos", headers=headers)
    assert response.json()["meta"]["total"] == 1
    assert response.json()["items"][0]["name"] == "Grãos a granel"


def test_product_endpoints_require_authentication(client):
    response = client.get("/api/v1/products")
    assert response.status_code == 401


def test_visualizador_role_cannot_create_product(client, db_session):
    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="readonly@empresa-teste.com", password="Sup3rSecret!", role_code="VISUALIZADOR")
    db_session.commit()
    login = client.post("/api/v1/auth/login", json={"email": "readonly@empresa-teste.com", "password": "Sup3rSecret!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post("/api/v1/products", headers=headers, json={"name": "Não deveria criar"})
    assert response.status_code == 403


def test_tenant_a_cannot_see_product_from_tenant_b(client, db_session):
    tenant_a = make_tenant(db_session, legal_name="Empresa A Ltda")
    tenant_b = make_tenant(db_session, legal_name="Empresa B Ltda")
    make_user(db_session, tenant_a, email="usera@a.com", password="Sup3rSecret!")
    make_user(db_session, tenant_b, email="userb@b.com", password="Sup3rSecret!")
    db_session.commit()

    headers_b = {
        "Authorization": "Bearer "
        + client.post("/api/v1/auth/login", json={"email": "userb@b.com", "password": "Sup3rSecret!"}).json()["access_token"]
    }
    headers_a = {
        "Authorization": "Bearer "
        + client.post("/api/v1/auth/login", json={"email": "usera@a.com", "password": "Sup3rSecret!"}).json()["access_token"]
    }

    created = client.post("/api/v1/products", headers=headers_b, json={"name": "Produto B"})
    product_b_id = created.json()["id"]

    assert client.get(f"/api/v1/products/{product_b_id}", headers=headers_a).status_code == 404
    assert client.get("/api/v1/products", headers=headers_a).json()["meta"]["total"] == 0


def test_schedule_item_with_product_exposes_name_and_unit(auth_client, db_session):
    from tests.backend.factories import make_route

    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()

    product = client.post(
        "/api/v1/products", headers=headers, json={"name": "Cimento CP-II", "unit_of_measure": "KG"},
    ).json()

    item = client.post(
        "/api/v1/schedules/items", headers=headers,
        json={
            "schedule_date": "2026-09-10", "shift": "MANHA", "route_id": route.id,
            "scheduled_at": "2026-09-10T07:00:00", "product_id": product["id"], "quantity": 200,
        },
    )
    assert item.status_code == 201
    body = item.json()
    assert body["product_name"] == "Cimento CP-II"
    assert body["unit_of_measure"] == "KG"


def test_schedule_item_rejects_product_from_another_tenant(auth_client, client, db_session):
    from tests.backend.factories import make_route

    _client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    other_tenant = make_tenant(db_session, legal_name="Outra Empresa Ltda")
    other_user = make_user(db_session, other_tenant, email="outro@outra.com", password="Sup3rSecret!")
    db_session.commit()

    other_headers = {
        "Authorization": "Bearer "
        + client.post("/api/v1/auth/login", json={"email": other_user.email, "password": "Sup3rSecret!"}).json()["access_token"]
    }
    foreign_product = client.post(
        "/api/v1/products", headers=other_headers, json={"name": "Produto de Outra Empresa"},
    ).json()

    response = client.post(
        "/api/v1/schedules/items", headers=headers,
        json={
            "schedule_date": "2026-09-10", "shift": "MANHA", "route_id": route.id,
            "scheduled_at": "2026-09-10T07:00:00", "product_id": foreign_product["id"],
        },
    )
    assert response.status_code == 422
