"""Teste obrigatório de isolamento multi-tenant com dados reais (seção 52/53).

"Empresa A NÃO consegue consultar Empresa B" — verificado aqui contra o
primeiro repositório tenant-scoped que existe (`UserRepository`). Qualquer
vazamento encontrado por este teste deve ser tratado como bug crítico,
conforme a especificação exige explicitamente.
"""
from app.repositories.user_repository import UserRepository
from tests.backend.factories import make_tenant, make_user


def test_tenant_a_cannot_list_users_from_tenant_b(db_session):
    tenant_a = make_tenant(db_session, legal_name="Empresa A Ltda")
    tenant_b = make_tenant(db_session, legal_name="Empresa B Ltda")
    make_user(db_session, tenant_a, email="userA@empresa-a.com")
    make_user(db_session, tenant_b, email="userB@empresa-b.com")
    db_session.commit()

    users_visible_to_a = UserRepository(db_session, tenant_a.id).list()
    users_visible_to_b = UserRepository(db_session, tenant_b.id).list()

    emails_visible_to_a = {u.email for u in users_visible_to_a}
    emails_visible_to_b = {u.email for u in users_visible_to_b}

    assert emails_visible_to_a == {"usera@empresa-a.com"}
    assert emails_visible_to_b == {"userb@empresa-b.com"}
    assert "userb@empresa-b.com" not in emails_visible_to_a
    assert "usera@empresa-a.com" not in emails_visible_to_b


def test_tenant_a_cannot_fetch_a_specific_user_from_tenant_b_by_id(db_session):
    tenant_a = make_tenant(db_session, legal_name="Empresa A Ltda")
    tenant_b = make_tenant(db_session, legal_name="Empresa B Ltda")
    make_user(db_session, tenant_a, email="usera2@empresa-a.com")
    user_b = make_user(db_session, tenant_b, email="userb2@empresa-b.com")
    db_session.commit()

    result = UserRepository(db_session, tenant_a.id).get(user_b.id)

    assert result is None


def test_login_tokens_are_scoped_to_the_correct_tenant(client, db_session):
    tenant_a = make_tenant(db_session, legal_name="Empresa A Ltda")
    tenant_b = make_tenant(db_session, legal_name="Empresa B Ltda")
    make_user(db_session, tenant_a, email="loginA@empresa-a.com", password="Sup3rSecret!")
    make_user(db_session, tenant_b, email="loginB@empresa-b.com", password="Sup3rSecret!")
    db_session.commit()

    response_a = client.post(
        "/api/v1/auth/login", json={"email": "loginA@empresa-a.com", "password": "Sup3rSecret!"}
    )
    response_b = client.post(
        "/api/v1/auth/login", json={"email": "loginB@empresa-b.com", "password": "Sup3rSecret!"}
    )

    assert response_a.json()["user"]["tenant_id"] == tenant_a.id
    assert response_b.json()["user"]["tenant_id"] == tenant_b.id
    assert response_a.json()["user"]["tenant_id"] != response_b.json()["user"]["tenant_id"]
