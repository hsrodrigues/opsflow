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


def test_route_coordinates_are_optional_and_feed_the_panel_map(auth_client):
    """Lat/long não afetam nada do resto do sistema — existem só pra alimentar
    o mapa do Painel de TV (`panel_service.get_board`)."""
    client, headers, _tenant = auth_client

    without_coords = client.post(
        "/api/v1/routes", headers=headers,
        json={"name": "Rota sem coordenadas", "origin_name": "Origem A", "destination_name": "Destino A"},
    )
    assert without_coords.status_code == 201
    body = without_coords.json()
    assert body["origin_latitude"] is None
    assert body["destination_latitude"] is None

    with_coords = client.post(
        "/api/v1/routes", headers=headers,
        json={
            "name": "Rota com coordenadas", "origin_name": "Origem B", "destination_name": "Destino B",
            "origin_latitude": -23.55, "origin_longitude": -46.63,
            "destination_latitude": -22.90, "destination_longitude": -43.20,
        },
    )
    assert with_coords.status_code == 201
    body = with_coords.json()
    assert body["origin_latitude"] == -23.55
    assert body["destination_longitude"] == -43.20

    route_id = with_coords.json()["id"]
    updated = client.patch(
        f"/api/v1/routes/{route_id}", headers=headers, json={"origin_latitude": -23.0, "origin_longitude": -47.0},
    )
    assert updated.status_code == 200
    assert updated.json()["origin_latitude"] == -23.0
    assert updated.json()["destination_latitude"] == -22.90  # não mexeu no que não foi enviado
