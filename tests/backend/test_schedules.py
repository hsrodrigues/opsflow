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


def test_delete_schedule_item_while_still_programado(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()
    item_id = _create_item(client, headers, route.id).json()["id"]

    response = client.delete(f"/api/v1/schedules/items/{item_id}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/api/v1/schedules/items/{item_id}", headers=headers).status_code == 404


def test_cannot_delete_schedule_item_once_it_becomes_an_operation(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()
    item_id = _create_item(client, headers, route.id).json()["id"]
    client.post(f"/api/v1/schedules/items/{item_id}/status", headers=headers, json={"status": "EM_OPERACAO"})

    response = client.delete(f"/api/v1/schedules/items/{item_id}", headers=headers)
    assert response.status_code == 422
    assert client.get(f"/api/v1/schedules/items/{item_id}", headers=headers).status_code == 200


def test_list_schedule_items_filters_by_date(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()
    _create_item(client, headers, route.id, schedule_date="2026-09-10")
    _create_item(client, headers, route.id, schedule_date="2026-09-11")

    response = client.get("/api/v1/schedules/items?schedule_date=2026-09-10", headers=headers)
    assert response.json()["meta"]["total"] == 1


def test_duplicate_schedule_clones_items_to_the_target_date(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()
    _create_item(client, headers, route.id, schedule_date="2026-09-10")
    second_item = _create_item(client, headers, route.id, schedule_date="2026-09-10").json()
    # Cancelado não deve ser duplicado.
    client.post(
        f"/api/v1/schedules/items/{second_item['id']}/status", headers=headers, json={"status": "CANCELADO"},
    )

    response = client.post(
        "/api/v1/schedules/duplicate", headers=headers,
        json={"source_date": "2026-09-10", "target_date": "2026-09-17"},
    )
    assert response.status_code == 200
    assert response.json()["items_created"] == 1

    cloned = client.get("/api/v1/schedules/items?schedule_date=2026-09-17", headers=headers).json()
    assert cloned["meta"]["total"] == 1
    assert cloned["items"][0]["status"] == "PROGRAMADO"
    assert cloned["items"][0]["scheduled_at"].startswith("2026-09-17")


def test_duplicate_schedule_rejects_same_source_and_target_date(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()
    _create_item(client, headers, route.id, schedule_date="2026-09-10")

    response = client.post(
        "/api/v1/schedules/duplicate", headers=headers,
        json={"source_date": "2026-09-10", "target_date": "2026-09-10"},
    )
    assert response.status_code == 422


def test_duplicate_schedule_requires_schedules_manage_permission(client, db_session):
    from tests.backend.factories import make_user

    tenant = make_tenant(db_session)
    make_user(db_session, tenant, email="viewer@dup-schedule.com", role_code="VISUALIZADOR")
    db_session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"email": "viewer@dup-schedule.com", "password": "Sup3rSecret!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/api/v1/schedules/duplicate", headers=headers,
        json={"source_date": "2026-09-10", "target_date": "2026-09-17"},
    )
    assert response.status_code == 403
