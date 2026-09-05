"""tenant panel token

Adiciona `tenants.panel_token`: um token de leitura opaco (gerado sob
demanda pelo backend, nunca pelo cliente) que autentica o painel de
operações somente-leitura (seção "painel de TV") sem exigir login — a TV do
centro de operações não tem teclado/2FA, então o acesso é por posse de um
link longo e não adivinhável, do jeito que um link de compartilhamento
funciona. Nullable porque a maioria dos tenants nunca vai gerar um; o
endpoint público resolve o tenant a partir do token, então ele precisa ser
único.

Revision ID: 59498a693e91
Revises: c5454c36bed1
Create Date: 2026-09-05 10:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = "59498a693e91"
down_revision = "c5454c36bed1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("panel_token", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_tenants_panel_token"), "tenants", ["panel_token"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_tenants_panel_token"), table_name="tenants")
    op.drop_column("tenants", "panel_token")
