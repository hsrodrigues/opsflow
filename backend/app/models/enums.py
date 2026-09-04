"""Enumerations shared across ORM models, schemas and services.

Centralizing them here keeps the database, the API layer and the desktop
client speaking exactly the same vocabulary for every status field.
"""
import enum


class LicenseStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    TRIAL = "TRIAL"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class PlanCode(str, enum.Enum):
    STARTER = "STARTER"
    PROFESSIONAL = "PROFESSIONAL"
    BUSINESS = "BUSINESS"
    ENTERPRISE = "ENTERPRISE"


class UserStatus(str, enum.Enum):
    ATIVO = "ATIVO"
    INATIVO = "INATIVO"
    BLOQUEADO = "BLOQUEADO"


class UserRoleCode(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN_EMPRESA = "ADMIN_EMPRESA"
    SUPERVISOR = "SUPERVISOR"
    OPERADOR = "OPERADOR"
    VISUALIZADOR = "VISUALIZADOR"


class VehicleStatus(str, enum.Enum):
    DISPONIVEL = "DISPONIVEL"
    EM_OPERACAO = "EM_OPERACAO"
    EM_MANUTENCAO = "EM_MANUTENCAO"
    INATIVO = "INATIVO"
    BLOQUEADO = "BLOQUEADO"


class DriverStatus(str, enum.Enum):
    ATIVO = "ATIVO"
    INATIVO = "INATIVO"
    BLOQUEADO = "BLOQUEADO"


class CarrierStatus(str, enum.Enum):
    ATIVO = "ATIVO"
    INATIVO = "INATIVO"
    BLOQUEADO = "BLOQUEADO"


class RouteStatus(str, enum.Enum):
    ATIVA = "ATIVA"
    INATIVA = "INATIVA"


class ScheduleStatus(str, enum.Enum):
    PROGRAMADO = "PROGRAMADO"
    AGUARDANDO = "AGUARDANDO"
    EM_FILA = "EM_FILA"
    EM_OPERACAO = "EM_OPERACAO"
    CONCLUIDO = "CONCLUIDO"
    ATRASADO = "ATRASADO"
    CANCELADO = "CANCELADO"


class OccurrenceSeverity(str, enum.Enum):
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    CRITICA = "CRITICA"


class OccurrenceStatus(str, enum.Enum):
    ABERTA = "ABERTA"
    EM_ANALISE = "EM_ANALISE"
    RESOLVIDA = "RESOLVIDA"
    CANCELADA = "CANCELADA"


class NotificationSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    SUCCESS = "SUCCESS"


class AuditAction(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    STATUS_CHANGE = "STATUS_CHANGE"
