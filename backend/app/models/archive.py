"""Archive tables (seção 41 "Automações" — arquivamento de dados antigos).

Espelham as colunas das tabelas vivas (`operations`, `schedule_items`,
`status_history`, `occurrences`) mais um `archived_at` — deliberadamente
mapeadas como classes **simples**, sem relationships nem mixins: uma vez
arquivada, a linha é um registro histórico passivo, não faz mais parte do
grafo relacional vivo. `tenant_id` mantém uma FK de verdade pra `tenants`
(a guarda estática de isolamento multi-tenant, `test_tenant_isolation_
schema.py`, exige isso de toda tabela com `tenant_id` — e é seguro aqui,
arquivar nunca mexe em `tenants`), mas nenhuma outra coluna tem FK de volta
pras tabelas de origem (`schedule_item_id`, `operation_id`, etc.) — essas
sim ficariam bloqueadas por integridade referencial justamente da tabela
que o próprio arquivamento está esvaziando.

Populadas de dois jeitos, sempre com a MESMA regra de negócio (ver
`app/services/archive_service.py`): em MySQL, pela stored procedure
`sp_archive_old_records` (criada na migration `20260905_..._stored_
procedures.py`); em qualquer outro dialeto (SQLite, usado pelos testes,
onde uma stored procedure não existe), por um fallback em Python/ORM que
insere nestas mesmas tabelas.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import OccurrenceSeverity, OccurrenceStatus, ScheduleStatus
from app.models.types import bigint_pk, enum_column


class OperationArchive(Base):
    __tablename__ = "operations_archive"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=False)
    tenant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    schedule_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operation_number: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[ScheduleStatus] = mapped_column(enum_column(ScheduleStatus, length=20), nullable=False)
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ScheduleItemArchive(Base):
    __tablename__ = "schedule_items_archive"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=False)
    tenant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    schedule_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    route_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    carrier_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    vehicle_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    driver_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    product_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cargo_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[ScheduleStatus] = mapped_column(enum_column(ScheduleStatus, length=20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class StatusHistoryArchive(Base):
    __tablename__ = "status_history_archive"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=False)
    tenant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    previous_status: Mapped[ScheduleStatus | None] = mapped_column(enum_column(ScheduleStatus, length=20), nullable=True)
    new_status: Mapped[ScheduleStatus] = mapped_column(enum_column(ScheduleStatus, length=20), nullable=False)
    changed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OccurrenceArchive(Base):
    __tablename__ = "occurrences_archive"

    id: Mapped[int] = mapped_column(bigint_pk(), primary_key=True, autoincrement=False)
    tenant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurrence_type_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    vehicle_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    driver_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    responsible_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[OccurrenceSeverity] = mapped_column(enum_column(OccurrenceSeverity, length=20), nullable=False)
    status: Mapped[OccurrenceStatus] = mapped_column(enum_column(OccurrenceStatus, length=20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
