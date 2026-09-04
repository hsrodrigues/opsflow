"""Tests for `/api/v1/schedules` (seção 13): programação e timeline de status."""
from tests.backend.factories import make_route, make_tenant


def _create_item(client, headers, route_id, *, schedule_date="2026-09-10"):
    return client.post(
        "/api/v1/schedules/items", headers=headers,
        json={
            "schedule_date": schedule_date, "shift": "MANHA", "route_id": route_id,
            "scheduled_at": "2026-09-10T07:00:00", "cargo_description": "Carga geral", "quantity": 10,
        },
    )


def test_create_schedule_item_starts_as_programado_without_operation(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()

    response = _create_item(client, headers, route.id)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PROGRAMADO"
    assert body["operation_number"] is None
    assert body["route_name"] == route.name


def test_status_change_creates_operation_and_records_history(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()
    item_id = _create_item(client, headers, route.id).json()["id"]

    response = client.post(
        f"/api/v1/schedules/items/{item_id}/status", headers=headers,
        json={"status": "EM_OPERACAO", "notes": "Iniciado no pátio"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "EM_OPERACAO"
    assert body["operation_number"] is not None

    history = client.get(f"/api/v1/schedules/items/{item_id}/history", headers=headers).json()
    assert len(history) == 1
    assert history[0]["previous_status"] == "PROGRAMADO"
    assert history[0]["new_status"] == "EM_OPERACAO"
    assert history[0]["notes"] == "Iniciado no pátio"


def test_multiple_status_changes_reuse_the_same_operation_number(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()
    item_id = _create_item(client, headers, route.id).json()["id"]

    first = client.post(
        f"/api/v1/schedules/items/{item_id}/status", headers=headers, json={"status": "AGUARDANDO"}
    ).json()
    second = client.post(
        f"/api/v1/schedules/items/{item_id}/status", headers=headers, json={"status": "EM_OPERACAO"}
    ).json()

    assert first["operation_number"] == second["operation_number"]

    history = client.get(f"/api/v1/schedules/items/{item_id}/history", headers=headers).json()
    assert len(history) == 2
    assert [h["new_status"] for h in history] == ["AGUARDANDO", "EM_OPERACAO"]


def test_create_schedule_item_rejects_route_from_another_tenant(auth_client, client, db_session):
    _client, headers, _tenant = auth_client
    other_tenant = make_tenant(db_session, legal_name="Outra Empresa Ltda")
    foreign_route = make_route(db_session, other_tenant, name="Rota de Outra Empresa")
    db_session.commit()

    response = _create_item(client, headers, foreign_route.id)
    assert response.status_code == 422


def test_list_schedule_items_filters_by_date(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()
    _create_item(client, headers, route.id, schedule_date="2026-09-10")
    _create_item(client, headers, route.id, schedule_date="2026-09-11")

    response = client.get("/api/v1/schedules/items?schedule_date=2026-09-10", headers=headers)
    assert response.json()["meta"]["total"] == 1
