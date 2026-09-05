"""license activation keys

Permite gerar uma `license_key` sem empresa ainda vinculada (self-
ativação, seção 6): `tenant_id` vira nullable, e `pending_trial_days`/
`activated_at` guardam o que uma chave "não reivindicada" precisa lembrar
até `POST /api/v1/activation/activate` preencher o resto.

Revision ID: a1c6e0c78bce
Revises: 5097ad520a5d
Create Date: 2026-09-04 16:04:33.330346
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1c6e0c78bce'
down_revision: Union[str, None] = '5097ad520a5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `batch_alter_table`, não `alter_column`/`add_column` soltos: o SQLite
    # (usado pelos testes) não suporta `ALTER TABLE ... ALTER COLUMN`, e o
    # tipo gerado pelo autogenerate (`mysql.BIGINT()`) é específico do
    # dialeto MySQL — trocado pelo `sa.BigInteger()` genérico (mesma
    # convenção de `..._products.py`).
    with op.batch_alter_table('licenses') as batch_op:
        batch_op.add_column(sa.Column('pending_trial_days', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('activated_at', sa.DateTime(), nullable=True))
        batch_op.alter_column('tenant_id', existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('licenses') as batch_op:
        batch_op.alter_column('tenant_id', existing_type=sa.BigInteger(), nullable=False)
        batch_op.drop_column('activated_at')
        batch_op.drop_column('pending_trial_days')
