"""stored_procedures_and_archive_tables

Três stored procedures pedidas explicitamente pelo cliente pra reduzir
processo manual ("poucos processos manuais"): duplicar a programação de um
dia pra outra data, fechar automaticamente operações penduradas há tempo
demais num status intermediário, e arquivar operações/ocorrências antigas
já concluídas pra fora das tabelas principais. As tabelas de arquivo (acima,
autogeradas) são portáveis e existem em qualquer dialeto; as PROCEDURES em
si são sintaxe exclusiva de MySQL (`CREATE PROCEDURE`/cursor/`SIGNAL` não
existem no SQLite usado pelos testes) — por isso ficam atrás de um guard de
dialeto, o mesmo padrão já usado nesta base pra evitar quebrar a suíte
(ver a nota de portabilidade em `docs/DATABASE.md`). A lógica de negócio
correspondente também existe em Python puro (`app/services/schedule_
service.py`, `operation_service.py`, `archive_service.py`) — usada de
verdade em qualquer banco que não seja MySQL, e é o que os testes
automatizados exercitam; a procedure é o caminho de produção (mais rápido,
uma única viagem ao banco, atômico).

Revision ID: c5454c36bed1
Revises: a1c6e0c78bce
Create Date: 2026-09-05 06:01:00.138736
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5454c36bed1'
down_revision: Union[str, None] = 'a1c6e0c78bce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SP_DUPLICATE_SCHEDULE_DAY = """
CREATE PROCEDURE sp_duplicate_schedule_day(
    IN p_tenant_id BIGINT,
    IN p_source_date DATE,
    IN p_target_date DATE,
    IN p_actor_user_id BIGINT
)
BEGIN
    DECLARE v_done INT DEFAULT FALSE;
    DECLARE v_source_schedule_id BIGINT;
    DECLARE v_shift VARCHAR(20);
    DECLARE v_target_schedule_id BIGINT;
    DECLARE v_items_created INT DEFAULT 0;
    DECLARE cur CURSOR FOR
        SELECT id, shift FROM schedules WHERE tenant_id = p_tenant_id AND schedule_date = p_source_date;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = TRUE;

    IF p_source_date = p_target_date THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A data de destino precisa ser diferente da data de origem.';
    END IF;

    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO v_source_schedule_id, v_shift;
        IF v_done THEN
            LEAVE read_loop;
        END IF;

        SET v_target_schedule_id = NULL;
        SELECT id INTO v_target_schedule_id FROM schedules
            WHERE tenant_id = p_tenant_id AND schedule_date = p_target_date AND shift = v_shift
            LIMIT 1;

        IF v_target_schedule_id IS NULL THEN
            INSERT INTO schedules (tenant_id, schedule_date, shift, notes, created_by, updated_by, created_at, updated_at)
            VALUES (p_tenant_id, p_target_date, v_shift, NULL, p_actor_user_id, p_actor_user_id, UTC_TIMESTAMP(), UTC_TIMESTAMP());
            SET v_target_schedule_id = LAST_INSERT_ID();
        END IF;

        INSERT INTO schedule_items (
            tenant_id, schedule_id, route_id, carrier_id, vehicle_id, driver_id, product_id,
            scheduled_at, cargo_description, quantity, notes, status,
            created_by, updated_by, created_at, updated_at
        )
        SELECT
            tenant_id, v_target_schedule_id, route_id, carrier_id, vehicle_id, driver_id, product_id,
            TIMESTAMP(p_target_date, TIME(scheduled_at)), cargo_description, quantity, notes, 'PROGRAMADO',
            p_actor_user_id, p_actor_user_id, UTC_TIMESTAMP(), UTC_TIMESTAMP()
        FROM schedule_items
        WHERE schedule_id = v_source_schedule_id AND deleted_at IS NULL AND status <> 'CANCELADO';

        SET v_items_created = v_items_created + ROW_COUNT();
    END LOOP;
    CLOSE cur;

    SELECT v_items_created AS items_created;
END
"""

_SP_CLOSE_STALE_OPERATIONS = """
CREATE PROCEDURE sp_close_stale_operations(
    IN p_tenant_id BIGINT,
    IN p_stale_after_hours INT
)
BEGIN
    DECLARE v_cutoff DATETIME;
    SET v_cutoff = UTC_TIMESTAMP() - INTERVAL p_stale_after_hours HOUR;

    CREATE TEMPORARY TABLE tmp_stale_ops AS
        SELECT o.id AS operation_id, o.status AS previous_status, si.id AS schedule_item_id
        FROM operations o
        JOIN schedule_items si ON si.id = o.schedule_item_id
        WHERE o.tenant_id = p_tenant_id
          AND o.status IN ('AGUARDANDO', 'EM_FILA', 'EM_OPERACAO')
          AND o.updated_at < v_cutoff;

    UPDATE operations o JOIN tmp_stale_ops t ON t.operation_id = o.id
        SET o.status = 'CANCELADO', o.updated_at = UTC_TIMESTAMP();

    UPDATE schedule_items si JOIN tmp_stale_ops t ON t.schedule_item_id = si.id
        SET si.status = 'CANCELADO', si.updated_at = UTC_TIMESTAMP();

    INSERT INTO status_history (tenant_id, operation_id, previous_status, new_status, changed_by, changed_at, notes)
    SELECT p_tenant_id, operation_id, previous_status, 'CANCELADO', NULL, UTC_TIMESTAMP(),
           CONCAT('Fechado automaticamente por rotina de limpeza — sem atualização há mais de ', p_stale_after_hours, ' hora(s).')
    FROM tmp_stale_ops;

    SELECT operation_id, schedule_item_id, previous_status FROM tmp_stale_ops;

    DROP TEMPORARY TABLE tmp_stale_ops;
END
"""

_SP_ARCHIVE_OLD_RECORDS = """
CREATE PROCEDURE sp_archive_old_records(
    IN p_tenant_id BIGINT,
    IN p_older_than_months INT
)
BEGIN
    DECLARE v_cutoff DATETIME;
    DECLARE v_ops_count INT DEFAULT 0;
    DECLARE v_occ_count INT DEFAULT 0;

    IF p_older_than_months < 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'older_than_months precisa ser pelo menos 1.';
    END IF;
    SET v_cutoff = UTC_TIMESTAMP() - INTERVAL p_older_than_months MONTH;

    -- Operações concluídas/canceladas antigas, SEM nenhuma ocorrência ainda
    -- vinculada (occurrences.operation_id não tem ON DELETE CASCADE de
    -- propósito — arquivar não pode arrastar uma ocorrência junto sem que
    -- ela mesma tenha sido avaliada pelos próprios critérios dela).
    CREATE TEMPORARY TABLE tmp_archive_ops AS
        SELECT o.id AS operation_id, o.schedule_item_id
        FROM operations o
        WHERE o.tenant_id = p_tenant_id
          AND o.status IN ('CONCLUIDO', 'CANCELADO')
          AND o.updated_at < v_cutoff
          AND NOT EXISTS (SELECT 1 FROM occurrences oc WHERE oc.operation_id = o.id);

    SELECT COUNT(*) INTO v_ops_count FROM tmp_archive_ops;

    IF v_ops_count > 0 THEN
        -- Colunas explícitas dos dois lados, de propósito: `SELECT o.*`
        -- casaria por POSIÇÃO, não por nome — e a ordem física das colunas
        -- diverge entre a tabela viva (mixins do SQLAlchemy acrescentam
        -- tenant_id/created_at/etc. no FIM da tabela) e a tabela de arquivo
        -- (declarada na ordem "lógica", tenant_id logo depois do id). Um
        -- `SELECT *` aqui deslocava cada valor uma posição, e o campo
        -- NOT NULL `status` acabava recebendo o `arrived_at` (nullable) de
        -- outra coluna — bug real, pego rodando isto de verdade contra o
        -- MySQL de dev antes de existir a lista explícita abaixo.
        INSERT INTO operations_archive (
            id, tenant_id, schedule_item_id, operation_number, status, arrived_at, started_at, completed_at,
            created_at, updated_at, created_by, updated_by, archived_at
        )
        SELECT
            o.id, o.tenant_id, o.schedule_item_id, o.operation_number, o.status, o.arrived_at, o.started_at,
            o.completed_at, o.created_at, o.updated_at, o.created_by, o.updated_by, UTC_TIMESTAMP()
        FROM operations o
        JOIN tmp_archive_ops t ON t.operation_id = o.id;

        INSERT INTO schedule_items_archive (
            id, tenant_id, schedule_id, route_id, carrier_id, vehicle_id, driver_id, product_id, scheduled_at,
            cargo_description, quantity, notes, status, created_at, updated_at, created_by, updated_by,
            deleted_at, archived_at
        )
        SELECT
            si.id, si.tenant_id, si.schedule_id, si.route_id, si.carrier_id, si.vehicle_id, si.driver_id,
            si.product_id, si.scheduled_at, si.cargo_description, si.quantity, si.notes, si.status,
            si.created_at, si.updated_at, si.created_by, si.updated_by, si.deleted_at, UTC_TIMESTAMP()
        FROM schedule_items si
        JOIN tmp_archive_ops t ON t.schedule_item_id = si.id;

        INSERT INTO status_history_archive (
            id, tenant_id, operation_id, previous_status, new_status, changed_by, changed_at, notes, archived_at
        )
        SELECT
            sh.id, sh.tenant_id, sh.operation_id, sh.previous_status, sh.new_status, sh.changed_by,
            sh.changed_at, sh.notes, UTC_TIMESTAMP()
        FROM status_history sh
        JOIN tmp_archive_ops t ON t.operation_id = sh.operation_id;

        -- Apagar schedule_items é suficiente: operations e status_history
        -- têm ON DELETE CASCADE de volta pra schedule_items/operations
        -- respectivamente (ver app/models/operation.py e status_history.py).
        DELETE si FROM schedule_items si JOIN tmp_archive_ops t ON t.schedule_item_id = si.id;
    END IF;
    DROP TEMPORARY TABLE tmp_archive_ops;

    -- Ocorrências resolvidas/canceladas antigas, sem anexo (attachments TEM
    -- ON DELETE CASCADE de occurrences — arquivar sem cópia perderia o
    -- anexo sem deixar rastro, então essas ficam de fora por enquanto).
    CREATE TEMPORARY TABLE tmp_archive_occ AS
        SELECT oc.id AS occurrence_id
        FROM occurrences oc
        WHERE oc.tenant_id = p_tenant_id
          AND oc.status IN ('RESOLVIDA', 'CANCELADA')
          AND oc.created_at < v_cutoff
          AND oc.deleted_at IS NULL
          AND NOT EXISTS (SELECT 1 FROM attachments a WHERE a.occurrence_id = oc.id);

    SELECT COUNT(*) INTO v_occ_count FROM tmp_archive_occ;

    IF v_occ_count > 0 THEN
        INSERT INTO occurrences_archive (
            id, tenant_id, occurrence_type_id, operation_id, vehicle_id, driver_id, responsible_user_id,
            description, severity, status, occurred_at, created_at, updated_at, created_by, updated_by,
            deleted_at, archived_at
        )
        SELECT
            oc.id, oc.tenant_id, oc.occurrence_type_id, oc.operation_id, oc.vehicle_id, oc.driver_id,
            oc.responsible_user_id, oc.description, oc.severity, oc.status, oc.occurred_at, oc.created_at,
            oc.updated_at, oc.created_by, oc.updated_by, oc.deleted_at, UTC_TIMESTAMP()
        FROM occurrences oc
        JOIN tmp_archive_occ t ON t.occurrence_id = oc.id;

        DELETE oc FROM occurrences oc JOIN tmp_archive_occ t ON t.occurrence_id = oc.id;
    END IF;
    DROP TEMPORARY TABLE tmp_archive_occ;

    SELECT v_ops_count AS operations_archived, v_occ_count AS occurrences_archived;
END
"""


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('occurrences_archive',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=False, nullable=False),
    sa.Column('tenant_id', sa.BigInteger(), nullable=False),
    sa.Column('occurrence_type_id', sa.BigInteger(), nullable=False),
    sa.Column('operation_id', sa.BigInteger(), nullable=True),
    sa.Column('vehicle_id', sa.BigInteger(), nullable=True),
    sa.Column('driver_id', sa.BigInteger(), nullable=True),
    sa.Column('responsible_user_id', sa.BigInteger(), nullable=True),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('severity', sa.Enum('BAIXA', 'MEDIA', 'ALTA', 'CRITICA', name='occurrenceseverity_enum', native_enum=False, length=20), nullable=False),
    sa.Column('status', sa.Enum('ABERTA', 'EM_ANALISE', 'RESOLVIDA', 'CANCELADA', name='occurrencestatus_enum', native_enum=False, length=20), nullable=False),
    sa.Column('occurred_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', sa.BigInteger(), nullable=True),
    sa.Column('updated_by', sa.BigInteger(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('archived_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_occurrences_archive_tenant_id'), 'occurrences_archive', ['tenant_id'], unique=False)
    op.create_table('operations_archive',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=False, nullable=False),
    sa.Column('tenant_id', sa.BigInteger(), nullable=False),
    sa.Column('schedule_item_id', sa.BigInteger(), nullable=False),
    sa.Column('operation_number', sa.String(length=20), nullable=False),
    sa.Column('status', sa.Enum('PROGRAMADO', 'AGUARDANDO', 'EM_FILA', 'EM_OPERACAO', 'CONCLUIDO', 'ATRASADO', 'CANCELADO', name='schedulestatus_enum', native_enum=False, length=20), nullable=False),
    sa.Column('arrived_at', sa.DateTime(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', sa.BigInteger(), nullable=True),
    sa.Column('updated_by', sa.BigInteger(), nullable=True),
    sa.Column('archived_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_operations_archive_tenant_id'), 'operations_archive', ['tenant_id'], unique=False)
    op.create_table('schedule_items_archive',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=False, nullable=False),
    sa.Column('tenant_id', sa.BigInteger(), nullable=False),
    sa.Column('schedule_id', sa.BigInteger(), nullable=False),
    sa.Column('route_id', sa.BigInteger(), nullable=False),
    sa.Column('carrier_id', sa.BigInteger(), nullable=True),
    sa.Column('vehicle_id', sa.BigInteger(), nullable=True),
    sa.Column('driver_id', sa.BigInteger(), nullable=True),
    sa.Column('product_id', sa.BigInteger(), nullable=True),
    sa.Column('scheduled_at', sa.DateTime(), nullable=False),
    sa.Column('cargo_description', sa.String(length=255), nullable=True),
    sa.Column('quantity', sa.Numeric(), nullable=True),
    sa.Column('notes', sa.String(length=1000), nullable=True),
    sa.Column('status', sa.Enum('PROGRAMADO', 'AGUARDANDO', 'EM_FILA', 'EM_OPERACAO', 'CONCLUIDO', 'ATRASADO', 'CANCELADO', name='schedulestatus_enum', native_enum=False, length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('created_by', sa.BigInteger(), nullable=True),
    sa.Column('updated_by', sa.BigInteger(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('archived_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_schedule_items_archive_tenant_id'), 'schedule_items_archive', ['tenant_id'], unique=False)
    op.create_table('status_history_archive',
    sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=False, nullable=False),
    sa.Column('tenant_id', sa.BigInteger(), nullable=False),
    sa.Column('operation_id', sa.BigInteger(), nullable=False),
    sa.Column('previous_status', sa.Enum('PROGRAMADO', 'AGUARDANDO', 'EM_FILA', 'EM_OPERACAO', 'CONCLUIDO', 'ATRASADO', 'CANCELADO', name='schedulestatus_enum', native_enum=False, length=20), nullable=True),
    sa.Column('new_status', sa.Enum('PROGRAMADO', 'AGUARDANDO', 'EM_FILA', 'EM_OPERACAO', 'CONCLUIDO', 'ATRASADO', 'CANCELADO', name='schedulestatus_enum', native_enum=False, length=20), nullable=False),
    sa.Column('changed_by', sa.BigInteger(), nullable=True),
    sa.Column('changed_at', sa.DateTime(), nullable=False),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('archived_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_status_history_archive_operation_id'), 'status_history_archive', ['operation_id'], unique=False)
    op.create_index(op.f('ix_status_history_archive_tenant_id'), 'status_history_archive', ['tenant_id'], unique=False)
    # ### end Alembic commands ###

    # Procedures são sintaxe exclusiva de MySQL — SQLite (testes) não
    # entende CREATE PROCEDURE/cursor/SIGNAL. Ver docstring do módulo.
    if op.get_bind().dialect.name == "mysql":
        op.execute(_SP_DUPLICATE_SCHEDULE_DAY)
        op.execute(_SP_CLOSE_STALE_OPERATIONS)
        op.execute(_SP_ARCHIVE_OLD_RECORDS)


def downgrade() -> None:
    if op.get_bind().dialect.name == "mysql":
        op.execute("DROP PROCEDURE IF EXISTS sp_archive_old_records")
        op.execute("DROP PROCEDURE IF EXISTS sp_close_stale_operations")
        op.execute("DROP PROCEDURE IF EXISTS sp_duplicate_schedule_day")

    # ### commands auto generated by Alembic - please adjust! ### (índices de
    # tenant_id removidos daqui: no MySQL, o índice sustenta a FK criada em
    # `sa.ForeignKeyConstraint` acima — soltar o índice antes de soltar a
    # tabela falha com "needed in a foreign key constraint"; `drop_table`
    # já remove índice e FK juntos, então soltar o índice à parte nunca era
    # necessário aqui.)
    op.drop_index(op.f('ix_status_history_archive_operation_id'), table_name='status_history_archive')
    op.drop_table('status_history_archive')
    op.drop_table('schedule_items_archive')
    op.drop_table('operations_archive')
    op.drop_table('occurrences_archive')
    # ### end Alembic commands ###
