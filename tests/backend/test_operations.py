"""Tests for `/api/v1/operations` — Centro de Operações (seção 21)."""
from tests.backend.factories import make_route


def _create_item(client, headers, route_id):
    return client.post(
        "/api/v1/schedules/items", headers=headers,
        json={
            "schedule_date": "2026-09-10", "shift": "MANHA", "route_id": route_id,
            "scheduled_at": "2026-09-10T07:00:00",
        },
    ).json()


def test_operations_list_excludes_concluded_and_cancelled(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()

    active_item = _create_item(client, headers, route.id)
    client.post(f"/api/v1/schedules/items/{active_item['id']}/status", headers=headers, json={"status": "EM_OPERACAO"})

    done_item = _create_item(client, headers, route.id)
    client.post(f"/api/v1/schedules/items/{done_item['id']}/status", headers=headers, json={"status": "EM_OPERACAO"})
    client.post(f"/api/v1/schedules/items/{done_item['id']}/status", headers=headers, json={"status": "CONCLUIDO"})

    response = client.get("/api/v1/operations", headers=headers)
    numbers = {op["status"] for op in response.json()}
    assert "CONCLUIDO" not in numbers
    assert "EM_OPERACAO" in numbers
    assert len(response.json()) == 1


def test_operations_summary_counts_by_status(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()

    programado = _create_item(client, headers, route.id)  # fica PROGRAMADO
    em_operacao = _create_item(client, headers, route.id)
    client.post(f"/api/v1/schedules/items/{em_operacao['id']}/status", headers=headers, json={"status": "EM_OPERACAO"})
    atrasado = _create_item(client, headers, route.id)
    client.post(f"/api/v1/schedules/items/{atrasado['id']}/status", headers=headers, json={"status": "ATRASADO"})

    response = client.get("/api/v1/operations/summary?date=2026-09-10", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body == {"programadas": 1, "em_operacao": 1, "atrasadas": 1}
