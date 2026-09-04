"""Tests for `/api/v1/drivers` (seção 10)."""
from app.models.carrier import Carrier
from tests.backend.factories import make_tenant


def test_create_driver_and_reject_duplicate_cpf(auth_client):
    client, headers, _tenant = auth_client
    payload = {"full_name": "João da Silva", "cpf": "123.456.789-00"}

    first = client.post("/api/v1/drivers", headers=headers, json=payload)
    assert first.status_code == 201
    assert first.json()["status"] == "ATIVO"

    duplicate = client.post(
        "/api/v1/drivers", headers=headers, json={**payload, "full_name": "Outro Nome"}
    )
    assert duplicate.status_code == 409


def test_create_driver_rejects_carrier_from_another_tenant(auth_client, client, db_session):
    _client, headers, tenant = auth_client
    other_tenant = make_tenant(db_session, legal_name="Outra Empresa Ltda")
    foreign_carrier = Carrier(tenant_id=other_tenant.id, legal_name="Transportadora de Outra Empresa")
    db_session.add(foreign_carrier)
    db_session.commit()

    response = client.post(
        "/api/v1/drivers", headers=headers,
        json={"full_name": "Motorista Teste", "cpf": "999.888.777-66", "carrier_id": foreign_carrier.id},
    )
    assert response.status_code == 422


def test_update_driver_status_and_soft_delete(auth_client):
    client, headers, _tenant = auth_client
    created = client.post(
        "/api/v1/drivers", headers=headers, json={"full_name": "Maria Souza", "cpf": "111.222.333-44"}
    )
    driver_id = created.json()["id"]

    updated = client.patch(f"/api/v1/drivers/{driver_id}", headers=headers, json={"status": "BLOQUEADO"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "BLOQUEADO"

    deleted = client.delete(f"/api/v1/drivers/{driver_id}", headers=headers)
    assert deleted.status_code == 204

    get_after_delete = client.get(f"/api/v1/drivers/{driver_id}", headers=headers)
    assert get_after_delete.status_code == 404
