"""Smoke tests for application bootstrap and the health check (seção 47)."""


def test_app_imports_and_exposes_expected_routes():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/health" in paths
    assert "/docs" in paths


def test_health_check_reports_ok_and_reachable_database(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert "version" in body
