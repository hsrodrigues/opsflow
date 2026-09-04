"""Tests for `/api/v1/dashboard` (seção 15/16)."""
from tests.backend.factories import make_route


def _create_item(client, headers, route_id, *, schedule_date="2026-09-10"):
    return client.post(
        "/api/v1/schedules/items", headers=headers,
        json={
            "schedule_date": schedule_date, "shift": "MANHA", "route_id": route_id,
            "scheduled_at": f"{schedule_date}T07:00:00",
        },
    ).json()


def test_dashboard_summary_reflects_operations_and_occurrences(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()

    concluded = _create_item(client, headers, route.id)
    client.post(f"/api/v1/schedules/items/{concluded['id']}/status", headers=headers, json={"status": "EM_OPERACAO"})
    client.post(f"/api/v1/schedules/items/{concluded['id']}/status", headers=headers, json={"status": "CONCLUIDO"})

    delayed = _create_item(client, headers, route.id)
    client.post(f"/api/v1/schedules/items/{delayed['id']}/status", headers=headers, json={"status": "ATRASADO"})

    cancelled = _create_item(client, headers, route.id)
    client.post(f"/api/v1/schedules/items/{cancelled['id']}/status", headers=headers, json={"status": "CANCELADO"})

    _create_item(client, headers, route.id)  # fica PROGRAMADO

    client.post(
        "/api/v1/occurrences", headers=headers,
        json={
            "occurrence_type_name": "Acidente", "description": "Teste dashboard.", "severity": "CRITICA",
            "occurred_at": "2026-09-10T09:00:00",
        },
    )

    response = client.get(
        "/api/v1/dashboard/summary?period_start=2026-09-10&period_end=2026-09-10", headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["concluidas"] == 1
    assert body["atrasadas"] == 1
    assert body["canceladas"] == 1
    assert body["ocorrencias"] == 1
    assert body["tempo_medio_minutos"] is not None
    assert body["taxa_conclusao_percentual"] == 25.0
    assert body["indice_atraso_percentual"] == 25.0


def test_dashboard_charts_group_by_status_and_severity(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()

    item = _create_item(client, headers, route.id)
    client.post(f"/api/v1/schedules/items/{item['id']}/status", headers=headers, json={"status": "EM_OPERACAO"})
    client.post(
        "/api/v1/occurrences", headers=headers,
        json={
            "occurrence_type_name": "Divergência", "description": "Teste.", "severity": "ALTA",
            "occurred_at": "2026-09-10T09:00:00",
        },
    )

    response = client.get(
        "/api/v1/dashboard/charts?period_start=2026-09-10&period_end=2026-09-10", headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    status_labels = {point["label"] for point in body["operacoes_por_status"]}
    assert "EM_OPERACAO" in status_labels
    severity_labels = {point["label"] for point in body["ocorrencias_por_severidade"]}
    assert "ALTA" in severity_labels
    assert sum(point["value"] for point in body["operacoes_por_dia"]) == 1


def test_dashboard_requires_authentication(client):
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 401
