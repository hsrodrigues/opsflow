"""Tests for `/api/v1/vehicles` (seção 9), incluindo o limite de plano (seção 6)."""
from app.models.license import License
from app.models.plan import Plan
from app.models.enums import LicenseStatus
from datetime import datetime, timedelta, timezone


def test_create_vehicle_and_reject_duplicate_plate(auth_client):
    client, headers, _tenant = auth_client
    payload = {"plate": "ABC1D23", "brand": "Volvo", "model": "FH 540"}

    first = client.post("/api/v1/vehicles", headers=headers, json=payload)
    assert first.status_code == 201
    assert first.json()["status"] == "DISPONIVEL"

    duplicate = client.post("/api/v1/vehicles", headers=headers, json={**payload, "brand": "Scania"})
    assert duplicate.status_code == 409


def test_vehicle_creation_respects_plan_limit(auth_client, db_session):
    client, headers, tenant = auth_client

    # STARTER permite só 100 veículos por padrão — reduzimos via override na
    # própria licença para tornar o teste rápido de rodar (1 veículo).
    starter_plan = db_session.query(Plan).filter(Plan.code == "STARTER").one()
    # issued_at no futuro: get_latest_license() ordena por issued_at desc, então
    # isso garante — sem depender da resolução do relógio — que esta license
    # (com o override) vence a já criada pela fixture auth_client.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(
        License(
            tenant_id=tenant.id, plan_id=starter_plan.id, license_key=f"limit-test-{tenant.id}",
            status=LicenseStatus.ACTIVE, issued_at=now + timedelta(minutes=1), expires_at=now + timedelta(days=30),
            max_vehicles=1,
        )
    )
    db_session.commit()

    first = client.post("/api/v1/vehicles", headers=headers, json={"plate": "AAA1111"})
    assert first.status_code == 201

    second = client.post("/api/v1/vehicles", headers=headers, json={"plate": "BBB2222"})
    assert second.status_code == 402
    assert second.json()["error"]["code"] == "OF-API-402"


def test_list_vehicles_filters_by_status_and_search(auth_client):
    client, headers, _tenant = auth_client
    client.post("/api/v1/vehicles", headers=headers, json={"plate": "CCC3333", "brand": "Volvo"})
    created = client.post("/api/v1/vehicles", headers=headers, json={"plate": "DDD4444", "brand": "Scania"})
    client.patch(
        f"/api/v1/vehicles/{created.json()['id']}", headers=headers, json={"status": "EM_MANUTENCAO"}
    )

    by_status = client.get("/api/v1/vehicles?status=EM_MANUTENCAO", headers=headers)
    assert by_status.json()["meta"]["total"] == 1
    assert by_status.json()["items"][0]["plate"] == "DDD4444"

    by_search = client.get("/api/v1/vehicles?q=Volvo", headers=headers)
    assert by_search.json()["meta"]["total"] == 1
    assert by_search.json()["items"][0]["plate"] == "CCC3333"
