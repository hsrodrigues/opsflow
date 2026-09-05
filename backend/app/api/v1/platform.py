"""`/api/v1/platform` — console de plataforma (seção 54), exclusivo de
`SUPER_ADMIN`: `/license-keys` gera chaves de ativação soltas (sem empresa
ainda — o cliente resgata em `/api/v1/activation/activate`), `/tenants`
gerencia empresas já ativadas e suas licenças. Nunca confundir com
`/api/v1/license` (leitura, pela própria empresa, da sua própria licença)
— aqui é quem opera o OpsFlow gerenciando terceiros.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import require_platform_admin
from app.core.database import get_db
from app.models.enums import AuditAction
from app.models.user import User
from app.schemas.platform import (
    ArchiveRequest,
    ArchiveResult,
    BackupOut,
    BackupRestoreRequest,
    LicenseKeyCreate,
    LicenseKeyOut,
    TenantCreate,
    TenantLicenseUpdate,
    TenantOut,
    TenantUpdate,
)
from app.services import archive_service, backup_service, tenant_service
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/platform", tags=["platform"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/license-keys", response_model=list[LicenseKeyOut])
def list_license_keys(
    _user: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> list[LicenseKeyOut]:
    return tenant_service.list_license_keys(db)


@router.post("/license-keys", response_model=LicenseKeyOut, status_code=201)
def generate_license_key(
    payload: LicenseKeyCreate, request: Request,
    user: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> LicenseKeyOut:
    return tenant_service.generate_license_key(db, user, payload, _client_ip(request))


@router.get("/tenants", response_model=list[TenantOut])
def list_tenants(
    _user: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> list[TenantOut]:
    return tenant_service.list_tenants(db)


@router.post("/tenants", response_model=TenantOut, status_code=201)
def create_tenant(
    payload: TenantCreate, request: Request,
    user: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> TenantOut:
    return tenant_service.create_tenant(db, user, payload, _client_ip(request))


@router.patch("/tenants/{tenant_id}", response_model=TenantOut)
def update_tenant(
    tenant_id: int, payload: TenantUpdate, request: Request,
    user: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> TenantOut:
    return tenant_service.update_tenant(db, user, tenant_id, payload, _client_ip(request))


@router.patch("/tenants/{tenant_id}/license", response_model=TenantOut)
def update_tenant_license(
    tenant_id: int, payload: TenantLicenseUpdate, request: Request,
    user: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> TenantOut:
    return tenant_service.update_tenant_license(db, user, tenant_id, payload, _client_ip(request))


@router.post("/tenants/{tenant_id}/license/regenerate-key", response_model=TenantOut)
def regenerate_license_key(
    tenant_id: int, request: Request,
    user: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> TenantOut:
    return tenant_service.regenerate_license_key(db, user, tenant_id, _client_ip(request))


def _backup_to_out(path) -> BackupOut:
    return BackupOut(
        filename=path.name, size_bytes=path.stat().st_size,
        created_at=backup_service.parse_backup_timestamp(path.name),
    )


@router.get("/backups", response_model=list[BackupOut])
def list_backups(_user: User = Depends(require_platform_admin)) -> list[BackupOut]:
    return [_backup_to_out(path) for path in backup_service.list_backups()]


@router.post("/backups", response_model=BackupOut, status_code=201)
def create_backup(
    request: Request, user: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> BackupOut:
    path = backup_service.create_backup()
    write_audit_log(
        db, tenant_id=None, user_id=user.id, action=AuditAction.BACKUP,
        table_name=None, record_id=path.name, ip_address=_client_ip(request),
    )
    db.commit()
    return _backup_to_out(path)


@router.post("/backups/restore", status_code=204)
def restore_backup(
    payload: BackupRestoreRequest, request: Request,
    user: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> None:
    # `user` veio de uma SELECT feita pela dependência `require_platform_admin`
    # nesta MESMA sessão/conexão, ainda numa transação aberta (o SQLAlchemy só
    # fecha a transação em commit/close — `get_db` só dá `close()` no fim do
    # request). Sob MySQL, essa transação aberta segura um metadata lock na
    # tabela `users` — e o `mysql` client chamado por `restore_backup` abaixo
    # precisa fazer `DROP TABLE`/`CREATE TABLE` em TODAS as tabelas do dump,
    # `users` incluída. Sem este `commit()` aqui, o restore trava esperando
    # esse lock que só seria liberado quando ESTE MESMO request terminasse —
    # um autodeadlock (bug real, reproduzido rodando o fluxo de verdade
    # contra o MySQL de dev antes deste `commit()` existir).
    ip_address = _client_ip(request)
    user_id = user.id
    db.commit()

    backup_service.restore_backup(payload.filename)

    write_audit_log(
        db, tenant_id=None, user_id=user_id, action=AuditAction.RESTORE,
        table_name=None, record_id=payload.filename, ip_address=ip_address,
    )
    db.commit()


@router.post("/archive", response_model=ArchiveResult)
def archive_old_records(
    payload: ArchiveRequest, request: Request,
    user: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> ArchiveResult:
    result = archive_service.archive_old_records_all_tenants(db, payload.older_than_months)
    write_audit_log(
        db, tenant_id=None, user_id=user.id, action=AuditAction.ARCHIVE,
        table_name=None, record_id=f"older_than_months={payload.older_than_months}", ip_address=_client_ip(request),
        new_value=result,
    )
    db.commit()
    return ArchiveResult(**result)
