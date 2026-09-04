"""Guarda estática de isolamento multi-tenant (seção 3/52/53).

O documento de especificação exige explicitamente um teste comprovando que
"Empresa A NÃO consegue consultar Empresa B" — os testes de ponta a ponta
com dados reais das duas empresas ficam para a Fase 9, quando repositories e
services existirem. Esta guarda cobre a pré-condição estrutural necessária
para aquele teste um dia poder passar: **toda tabela de dado de negócio
precisa ter uma coluna `tenant_id`** — se alguém adicionar uma tabela nova
sem essa coluna, este teste falha imediatamente, muito antes de qualquer
vazamento de dados chegar a acontecer em produção.
"""
from app.models import Base

# Tabelas legitimamente sem `tenant_id`: dado de referência global do
# sistema (não pertence a nenhum tenant específico), o próprio tenant, ou
# uma tabela escopada por `user_id` cujo isolamento por tenant é obtido
# indiretamente via `users.tenant_id` (refresh/reset tokens só existem
# atrelados a um usuário já autenticado, nunca consultados "soltos").
_GLOBAL_TABLES = {
    "tenants",
    "plans",
    "roles",
    "permissions",
    "role_permissions",
    "alembic_version",
    "refresh_tokens",
    "password_reset_tokens",
}


def test_every_business_table_has_a_tenant_id_column():
    tables_missing_tenant_id = [
        table_name
        for table_name, table in Base.metadata.tables.items()
        if table_name not in _GLOBAL_TABLES and "tenant_id" not in table.columns
    ]

    assert tables_missing_tenant_id == [], (
        "As tabelas a seguir não possuem tenant_id e vazariam dados entre "
        f"empresas se usadas sem isolamento: {tables_missing_tenant_id}. "
        "Adicione TenantMixin ao modelo ou inclua a tabela em _GLOBAL_TABLES "
        "se ela for legitimamente um dado de referência global."
    )


def test_every_tenant_id_column_is_a_foreign_key_to_tenants():
    for table_name, table in Base.metadata.tables.items():
        if "tenant_id" not in table.columns:
            continue
        tenant_id_column = table.columns["tenant_id"]
        referenced_tables = {fk.column.table.name for fk in tenant_id_column.foreign_keys}
        assert referenced_tables == {"tenants"}, (
            f"{table_name}.tenant_id deveria ser FK para tenants.id, encontrado: {referenced_tables}"
        )
