"""Tests for `/api/v1/panel` — o painel de operações (TV) público por token.

O board em si (`GET /panel/{token}/board`) é a única rota de negócio do
sistema que responde sem `Authorization` de propósito (ver o docstring do
router) — por isso boa parte destes testes chama `client.get(...)` sem
`headers`, deliberadamente.
"""
from datetime import date

from tests.backend.factories import make_license, make_route, make_tenant, make_user


def _create_item(client, headers, route_id, *, status=None):
    today = date.today().isoformat()
    response = client.post(
        "/api/v1/schedules/items", headers=headers,
        json={
            "schedule_date": today, "shift": "MANHA", "route_id": route_id,
            "scheduled_at": f"{today}T08:00:00", "cargo_description": "Carga teste", "quantity": 5,
        },
    )
    assert response.status_code == 201, response.text
    item = response.json()
    if status:
        response = client.post(
            f"/api/v1/schedules/items/{item['id']}/status", headers=headers, json={"status": status},
        )
        assert response.status_code == 200, response.text
        item = response.json()
    return item


def test_get_panel_token_creates_one_lazily(auth_client):
    client, headers, _tenant = auth_client
    response = client.get("/api/v1/panel/token", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["token"]) > 20
    assert body["board_path"] == f"/painel/{body['token']}"


def test_get_panel_token_is_stable_across_calls(auth_client):
    client, headers, _tenant = auth_client
    first = client.get("/api/v1/panel/token", headers=headers).json()["token"]
    second = client.get("/api/v1/panel/token", headers=headers).json()["token"]
    assert first == second


def test_regenerate_panel_token_invalidates_the_old_link(auth_client):
    client, headers, _tenant = auth_client
    old_token = client.get("/api/v1/panel/token", headers=headers).json()["token"]
    new_token = client.post("/api/v1/panel/token/regenerate", headers=headers).json()["token"]
    assert new_token != old_token

    assert client.get(f"/api/v1/panel/{old_token}/board").status_code == 404
    assert client.get(f"/api/v1/panel/{new_token}/board").status_code == 200


def test_panel_board_needs_no_authentication(auth_client):
    client, headers, _tenant = auth_client
    token = client.get("/api/v1/panel/token", headers=headers).json()["token"]

    response = client.get(f"/api/v1/panel/{token}/board")  # sem Authorization de propósito
    assert response.status_code == 200


def test_unknown_panel_token_returns_404(client):
    assert client.get("/api/v1/panel/token-que-nao-existe/board").status_code == 404


def test_getting_or_regenerating_the_token_requires_settings_permission(auth_client, db_session):
    client, _admin_headers, tenant = auth_client
    make_user(db_session, tenant, email="operador@auth-client-fixture.com", role_code="OPERADOR")
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"email": "operador@auth-client-fixture.com", "password": "Sup3rSecret!"},
    )
    operator_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/panel/token", headers=operator_headers).status_code == 403


def test_panel_board_lists_todays_operations_and_excludes_cancelled(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant, name="Rota Ativa")
    cancelled_route = make_route(db_session, tenant, name="Rota Cancelada")
    db_session.commit()

    _create_item(client, headers, route.id, status="EM_OPERACAO")
    _create_item(client, headers, cancelled_route.id, status="CANCELADO")

    token = client.get("/api/v1/panel/token", headers=headers).json()["token"]
    board = client.get(f"/api/v1/panel/{token}/board").json()

    assert board["tenant_name"]
    assert board["summary"]["em_operacao"] == 1
    route_names = [op["route_name"] for op in board["operations"]]
    assert "Rota Ativa" in route_names
    assert "Rota Cancelada" not in route_names


def test_panel_board_is_isolated_per_tenant(auth_client, db_session):
    client, headers, tenant_a = auth_client
    route_a = make_route(db_session, tenant_a, name="Rota Tenant A")
    db_session.commit()
    _create_item(client, headers, route_a.id, status="EM_OPERACAO")
    token_a = client.get("/api/v1/panel/token", headers=headers).json()["token"]

    tenant_b = make_tenant(db_session, legal_name="Empresa B Ltda")
    make_license(db_session, tenant_b)
    make_user(db_session, tenant_b, email="admin@empresa-b.com")
    db_session.commit()
    login_b = client.post("/api/v1/auth/login", json={"email": "admin@empresa-b.com", "password": "Sup3rSecret!"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}
    token_b = client.get("/api/v1/panel/token", headers=headers_b).json()["token"]

    board_a = client.get(f"/api/v1/panel/{token_a}/board").json()
    assert [op["route_name"] for op in board_a["operations"]] == ["Rota Tenant A"]

    board_b = client.get(f"/api/v1/panel/{token_b}/board").json()
    assert board_b["operations"] == []
