"""Tests for `/api/v1/occurrences` (seção 14)."""
from app.models.occurrence_type import OccurrenceType


def test_create_occurrence_creates_type_and_sets_responsible_user(auth_client, db_session):
    client, headers, tenant = auth_client

    response = client.post(
        "/api/v1/occurrences", headers=headers,
        json={
            "occurrence_type_name": "Atraso", "description": "Trânsito intenso na rodovia.",
            "severity": "MEDIA", "occurred_at": "2026-09-10T08:30:00",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["occurrence_type_name"] == "Atraso"
    assert body["status"] == "ABERTA"
    assert body["responsible_user_name"] is not None

    occurrence_type = db_session.query(OccurrenceType).filter(
        OccurrenceType.tenant_id == tenant.id, OccurrenceType.name == "Atraso"
    ).one_or_none()
    assert occurrence_type is not None


def test_reusing_same_type_name_does_not_duplicate_it(auth_client, db_session):
    client, headers, tenant = auth_client
    payload = {"occurrence_type_name": "Quebra", "description": "Pneu furado.", "occurred_at": "2026-09-10T09:00:00"}
    client.post("/api/v1/occurrences", headers=headers, json=payload)
    client.post("/api/v1/occurrences", headers=headers, json={**payload, "description": "Outra quebra."})

    types = db_session.query(OccurrenceType).filter(
        OccurrenceType.tenant_id == tenant.id, OccurrenceType.name == "Quebra"
    ).all()
    assert len(types) == 1


def test_filter_occurrences_by_severity(auth_client):
    client, headers, _tenant = auth_client
    client.post(
        "/api/v1/occurrences", headers=headers,
        json={
            "occurrence_type_name": "Acidente", "description": "Colisão leve.", "severity": "CRITICA",
            "occurred_at": "2026-09-10T10:00:00",
        },
    )
    client.post(
        "/api/v1/occurrences", headers=headers,
        json={
            "occurrence_type_name": "Divergência", "description": "Quantidade divergente.", "severity": "BAIXA",
            "occurred_at": "2026-09-10T11:00:00",
        },
    )

    response = client.get("/api/v1/occurrences?severity=CRITICA", headers=headers)
    assert response.json()["meta"]["total"] == 1
    assert response.json()["items"][0]["severity"] == "CRITICA"


def test_update_occurrence_status(auth_client):
    client, headers, _tenant = auth_client
    created = client.post(
        "/api/v1/occurrences", headers=headers,
        json={"occurrence_type_name": "Outros", "description": "Teste.", "occurred_at": "2026-09-10T12:00:00"},
    ).json()

    response = client.patch(
        f"/api/v1/occurrences/{created['id']}", headers=headers, json={"status": "RESOLVIDA"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVIDA"


def test_occurrence_endpoints_require_authentication(client):
    response = client.get("/api/v1/occurrences")
    assert response.status_code == 401


def test_accident_occurrence_auto_blocks_vehicle_and_notifies_admins(auth_client, db_session):
    """A automação da seção 41: um acidente registrado contra um veículo
    bloqueia esse veículo na mesma transação e notifica ADMIN_EMPRESA/
    SUPERVISOR — sem precisar de nenhum robô em background, é síncrono."""
    from app.models.notification import Notification
    from app.models.user import User

    client, headers, tenant = auth_client
    vehicle = client.post("/api/v1/vehicles", headers=headers, json={"plate": "ACD1D01"}).json()
    assert vehicle["status"] == "DISPONIVEL"

    response = client.post(
        "/api/v1/occurrences", headers=headers,
        json={
            "occurrence_type_name": "Acidente", "description": "Colisão traseira no pátio.",
            "severity": "CRITICA", "occurred_at": "2026-09-10T09:00:00", "vehicle_id": vehicle["id"],
        },
    )
    assert response.status_code == 201

    updated_vehicle = client.get(f"/api/v1/vehicles/{vehicle['id']}", headers=headers).json()
    assert updated_vehicle["status"] == "BLOQUEADO"

    admin = db_session.query(User).filter(User.tenant_id == tenant.id).one()
    notification = db_session.query(Notification).filter(
        Notification.tenant_id == tenant.id, Notification.user_id == admin.id,
        Notification.related_entity_type == "vehicle",
    ).one_or_none()
    assert notification is not None
    assert vehicle["plate"] in notification.message


def test_non_accident_occurrence_does_not_block_vehicle(auth_client):
    client, headers, _tenant = auth_client
    vehicle = client.post("/api/v1/vehicles", headers=headers, json={"plate": "NBL1D02"}).json()

    client.post(
        "/api/v1/occurrences", headers=headers,
        json={
            "occurrence_type_name": "Atraso", "description": "Trânsito intenso.", "severity": "BAIXA",
            "occurred_at": "2026-09-10T09:00:00", "vehicle_id": vehicle["id"],
        },
    )

    updated_vehicle = client.get(f"/api/v1/vehicles/{vehicle['id']}", headers=headers).json()
    assert updated_vehicle["status"] != "BLOQUEADO"


def test_accident_occurrence_does_not_reblock_already_blocked_vehicle(auth_client, db_session):
    """Idempotente: um segundo acidente no mesmo veículo já bloqueado não
    deve gerar uma segunda notificação de bloqueio."""
    from app.models.notification import Notification

    client, headers, tenant = auth_client
    vehicle = client.post("/api/v1/vehicles", headers=headers, json={"plate": "DBL1D03"}).json()

    for _ in range(2):
        client.post(
            "/api/v1/occurrences", headers=headers,
            json={
                "occurrence_type_name": "Acidente", "description": "Acidente.", "severity": "ALTA",
                "occurred_at": "2026-09-10T09:00:00", "vehicle_id": vehicle["id"],
            },
        )

    block_notifications = db_session.query(Notification).filter(
        Notification.tenant_id == tenant.id, Notification.related_entity_type == "vehicle",
        Notification.related_entity_id == vehicle["id"],
    ).count()
    assert block_notifications == 1


def test_critical_occurrence_auto_blocks_driver_and_notifies_admins(auth_client, db_session):
    """Pedido explícito do cliente: "bloquear motorista caso a ocorrência
    seja muito severa" — mesmo padrão do bloqueio automático de veículo em
    acidente, síncrono, mesma transação."""
    from app.models.notification import Notification
    from app.models.user import User

    client, headers, tenant = auth_client
    driver = client.post(
        "/api/v1/drivers", headers=headers, json={"full_name": "Motorista Crítico", "cpf": "111.222.333-44"},
    ).json()
    assert driver["status"] == "ATIVO"

    response = client.post(
        "/api/v1/occurrences", headers=headers,
        json={
            "occurrence_type_name": "Direção perigosa", "description": "Ultrapassagem em local proibido.",
            "severity": "CRITICA", "occurred_at": "2026-09-10T09:00:00", "driver_id": driver["id"],
        },
    )
    assert response.status_code == 201

    updated_driver = client.get(f"/api/v1/drivers/{driver['id']}", headers=headers).json()
    assert updated_driver["status"] == "BLOQUEADO"

    admin = db_session.query(User).filter(User.tenant_id == tenant.id).one()
    notification = db_session.query(Notification).filter(
        Notification.tenant_id == tenant.id, Notification.user_id == admin.id,
        Notification.related_entity_type == "driver",
    ).one_or_none()
    assert notification is not None
    assert driver["full_name"] in notification.message


def test_non_critical_occurrence_does_not_block_driver(auth_client):
    client, headers, _tenant = auth_client
    driver = client.post(
        "/api/v1/drivers", headers=headers, json={"full_name": "Motorista Tranquilo", "cpf": "555.666.777-88"},
    ).json()

    client.post(
        "/api/v1/occurrences", headers=headers,
        json={
            "occurrence_type_name": "Atraso", "description": "Trânsito intenso.", "severity": "ALTA",
            "occurred_at": "2026-09-10T09:00:00", "driver_id": driver["id"],
        },
    )

    updated_driver = client.get(f"/api/v1/drivers/{driver['id']}", headers=headers).json()
    assert updated_driver["status"] != "BLOQUEADO"


def test_critical_occurrence_does_not_reblock_already_blocked_driver(auth_client, db_session):
    """Idempotente, mesmo raciocínio do veículo: uma segunda ocorrência
    crítica contra o mesmo motorista já bloqueado não gera uma segunda
    notificação de bloqueio."""
    from app.models.notification import Notification

    client, headers, tenant = auth_client
    driver = client.post(
        "/api/v1/drivers", headers=headers, json={"full_name": "Motorista Reincidente", "cpf": "999.888.777-66"},
    ).json()

    for _ in range(2):
        client.post(
            "/api/v1/occurrences", headers=headers,
            json={
                "occurrence_type_name": "Direção perigosa", "description": "Ocorrência grave.",
                "severity": "CRITICA", "occurred_at": "2026-09-10T09:00:00", "driver_id": driver["id"],
            },
        )

    block_notifications = db_session.query(Notification).filter(
        Notification.tenant_id == tenant.id, Notification.related_entity_type == "driver",
        Notification.related_entity_id == driver["id"],
    ).count()
    assert block_notifications == 1
