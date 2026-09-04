"""Tests for `/api/v1/routes` (seção 12)."""


def test_create_route_creates_locations_and_lists_by_name(auth_client):
    client, headers, _tenant = auth_client

    response = client.post(
        "/api/v1/routes", headers=headers,
        json={
            "name": "São Paulo → Campinas", "origin_name": "CD São Paulo", "destination_name": "CD Campinas",
            "distance_km": 99.5, "estimated_time_minutes": 90,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["origin_name"] == "CD São Paulo"
    assert body["destination_name"] == "CD Campinas"
    assert body["status"] == "ATIVA"

    listing = client.get("/api/v1/routes?q=Campinas", headers=headers)
    assert listing.json()["meta"]["total"] == 1


def test_reusing_the_same_location_name_does_not_duplicate_it(auth_client, client, db_session):
    _client, headers, tenant = auth_client
    client.post(
        "/api/v1/routes", headers=headers,
        json={"name": "Rota 1", "origin_name": "CD São Paulo", "destination_name": "CD Rio"},
    )
    client.post(
        "/api/v1/routes", headers=headers,
        json={"name": "Rota 2", "origin_name": "CD São Paulo", "destination_name": "CD Belo Horizonte"},
    )

    from app.models.location import Location

    locations = (
        db_session.query(Location)
        .filter(Location.tenant_id == tenant.id, Location.name == "CD São Paulo")
        .all()
    )
    assert len(locations) == 1  # reaproveitado, não duplicado


def test_update_route_status_and_soft_delete(auth_client):
    client, headers, _tenant = auth_client
    created = client.post(
        "/api/v1/routes", headers=headers,
        json={"name": "Rota Teste", "origin_name": "Origem X", "destination_name": "Destino Y"},
    )
    route_id = created.json()["id"]

    updated = client.patch(f"/api/v1/routes/{route_id}", headers=headers, json={"status": "INATIVA"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "INATIVA"

    deleted = client.delete(f"/api/v1/routes/{route_id}", headers=headers)
    assert deleted.status_code == 204

    get_after_delete = client.get(f"/api/v1/routes/{route_id}", headers=headers)
    assert get_after_delete.status_code == 404


def test_route_endpoints_require_authentication(client):
    response = client.get("/api/v1/routes")
    assert response.status_code == 401
