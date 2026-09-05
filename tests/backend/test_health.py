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
    assert "database_host" in body


def test_database_host_never_leaks_the_password():
    """`/api/health` não exige autenticação nenhuma — vazar a senha do
    banco aqui seria grave. Testa a função de sanitização diretamente com
    uma senha "óbvia" que apareceria na resposta se o redact falhasse."""
    from app.api.health import _database_host

    host = _database_host("mysql+pymysql://root:SenhaSecreta123@127.0.0.1:3306/opsflow_db")
    assert host == "127.0.0.1:3306/opsflow_db"
    assert "SenhaSecreta123" not in host
    assert "root" not in host
