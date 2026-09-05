"""Tests for `/api/v1/reports` (seção 17): prévia (JSON) e exportação
(Excel/CSV/PDF) — cada tipo reaproveita os mesmos dados já testados em
seus próprios módulos, então aqui o foco é a montagem do relatório e a
geração dos três formatos de arquivo."""
from tests.backend.factories import make_route


def test_preview_operacoes_report(auth_client, db_session):
    client, headers, tenant = auth_client
    route = make_route(db_session, tenant)
    db_session.commit()
    client.post(
        "/api/v1/schedules/items", headers=headers,
        json={
            "schedule_date": "2026-09-10", "shift": "MANHA", "route_id": route.id,
            "scheduled_at": "2026-09-10T07:00:00",
        },
    )

    response = client.get(
        "/api/v1/reports/preview?report_type=operacoes&period_start=2026-09-01&period_end=2026-09-30",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 1
    assert "Rota" in body["columns"]
    assert body["rows"][0][2] == route.name


def test_preview_each_report_type_returns_expected_columns(auth_client):
    client, headers, _tenant = auth_client
    expected_columns = {
        "operacoes": "Nº operação", "ocorrencias": "Descrição", "veiculos": "Placa", "transportadoras": "Eficiência",
    }
    for report_type, must_have_column in expected_columns.items():
        response = client.get(f"/api/v1/reports/preview?report_type={report_type}", headers=headers)
        assert response.status_code == 200, response.text
        assert must_have_column in response.json()["columns"]


def test_preview_rejects_invalid_report_type(auth_client):
    client, headers, _tenant = auth_client
    response = client.get("/api/v1/reports/preview?report_type=inexistente", headers=headers)
    assert response.status_code == 422


def test_export_xlsx_returns_valid_spreadsheet(auth_client):
    import io

    from openpyxl import load_workbook

    client, headers, _tenant = auth_client
    response = client.get("/api/v1/reports/export?report_type=veiculos&format=xlsx", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")

    workbook = load_workbook(io.BytesIO(response.content))
    sheet = workbook.active
    assert sheet["A1"].value == "Relatório de Veículos"


def test_export_csv_starts_with_utf8_bom_and_title(auth_client):
    client, headers, _tenant = auth_client
    response = client.get("/api/v1/reports/export?report_type=ocorrencias&format=csv", headers=headers)
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")  # BOM: essencial pro Excel abrir acentos certo
    assert "Relatório de Ocorrências" in response.content.decode("utf-8-sig")


def test_export_pdf_returns_valid_pdf_header(auth_client):
    client, headers, _tenant = auth_client
    response = client.get("/api/v1/reports/export?report_type=transportadoras&format=pdf", headers=headers)
    assert response.status_code == 200
    assert response.content[:5] == b"%PDF-"


def test_export_rejects_invalid_format(auth_client):
    client, headers, _tenant = auth_client
    response = client.get("/api/v1/reports/export?report_type=veiculos&format=docx", headers=headers)
    assert response.status_code == 422


def test_reports_require_export_permission_not_just_view(client, db_session):
    from tests.backend.factories import make_tenant, make_user

    tenant = make_tenant(db_session)
    # OPERADOR não tem reports.view nem reports.export (ver seção 4) — cobre
    # os dois endpoints exigindo autenticação com o papel certo.
    make_user(db_session, tenant, email="operador@empresa-teste.com", password="Sup3rSecret!", role_code="OPERADOR")
    db_session.commit()
    login = client.post("/api/v1/auth/login", json={"email": "operador@empresa-teste.com", "password": "Sup3rSecret!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/reports/preview?report_type=veiculos", headers=headers).status_code == 403
    assert client.get("/api/v1/reports/export?report_type=veiculos&format=xlsx", headers=headers).status_code == 403


def test_reports_endpoints_require_authentication(client):
    response = client.get("/api/v1/reports/preview?report_type=veiculos")
    assert response.status_code == 401
