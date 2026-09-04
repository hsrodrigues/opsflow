"""Tests for `/api/v1/notifications` (seção 20)."""
from app.models.enums import NotificationSeverity
from app.models.notification import Notification
from app.models.user import User
from tests.backend.factories import make_tenant, make_user


def test_user_sees_own_and_broadcast_notifications_only(auth_client, db_session):
    client, headers, tenant = auth_client

    other_tenant = make_tenant(db_session, legal_name="Outra Empresa Ltda")
    other_user = make_user(db_session, other_tenant, email="outro@outra.com")

    # Pega o usuário "admin@auth-client-fixture.com" desta empresa (criado pela fixture auth_client).
    me = db_session.query(User).filter(User.tenant_id == tenant.id).one()

    db_session.add_all([
        Notification(tenant_id=tenant.id, user_id=me.id, title="Minha notificação", message="Só minha"),
        Notification(tenant_id=tenant.id, user_id=None, title="Aviso geral", message="Para todo mundo"),
        Notification(tenant_id=other_tenant.id, user_id=other_user.id, title="De outra empresa", message="Não deveria aparecer"),
    ])
    db_session.commit()

    response = client.get("/api/v1/notifications", headers=headers)
    assert response.status_code == 200
    titles = {item["title"] for item in response.json()["items"]}
    assert titles == {"Minha notificação", "Aviso geral"}


def test_mark_notification_as_read(auth_client, db_session):
    client, headers, tenant = auth_client
    me = db_session.query(User).filter(User.tenant_id == tenant.id).one()
    notification = Notification(tenant_id=tenant.id, user_id=me.id, title="Teste", message="Mensagem de teste")
    db_session.add(notification)
    db_session.commit()

    unread = client.get("/api/v1/notifications?unread_only=true", headers=headers)
    assert unread.json()["meta"]["total"] == 1

    response = client.post(f"/api/v1/notifications/{notification.id}/read", headers=headers)
    assert response.status_code == 200
    assert response.json()["read_at"] is not None

    unread_after = client.get("/api/v1/notifications?unread_only=true", headers=headers)
    assert unread_after.json()["meta"]["total"] == 0


def test_mark_all_notifications_read(auth_client, db_session):
    client, headers, tenant = auth_client
    me = db_session.query(User).filter(User.tenant_id == tenant.id).one()
    db_session.add_all([
        Notification(
            tenant_id=tenant.id, user_id=me.id, title=f"Notificação {i}", message="msg",
            severity=NotificationSeverity.INFO,
        )
        for i in range(3)
    ])
    db_session.commit()

    response = client.post("/api/v1/notifications/read-all", headers=headers)
    assert response.status_code == 200
    assert response.json()["marked"] == 3

    unread_after = client.get("/api/v1/notifications?unread_only=true", headers=headers)
    assert unread_after.json()["meta"]["total"] == 0
