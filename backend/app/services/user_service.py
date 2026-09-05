"""User service — gestão de equipe dentro do tenant (seção 4/5).

`SUPER_ADMIN` nunca é atribuível por aqui (ver `ASSIGNABLE_ROLE_CODES`) e um
usuário nunca desativa a própria conta por esta rota — as duas checagens
que existem só porque isto é gerido pelos próprios usuários da empresa, não
por uma plataforma central.
"""
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.security import hash_password
from app.models.enums import AuditAction
from app.models.role import Role
from app.models.user import User
from app.repositories.user_repository import UserRepository, get_user_by_email
from app.schemas.user import ASSIGNABLE_ROLE_CODES, UserCreate, UserOut, UserPasswordReset, UserUpdate
from app.services.audit_service import write_audit_log
from app.services.license_service import enforce_user_limit


def _role_or_400(db: Session, role_code: str) -> Role:
    if role_code not in ASSIGNABLE_ROLE_CODES:
        raise ValidationFailedError(f"Papel inválido: {role_code!r}.")
    role = db.query(Role).filter(Role.code == role_code).one_or_none()
    if role is None:
        raise ValidationFailedError(f"Papel inválido: {role_code!r}.")
    return role


def user_to_out(user: User) -> UserOut:
    role = user.roles[0] if user.roles else None
    return UserOut(
        id=user.id, email=user.email, full_name=user.full_name, phone=user.phone, status=user.status,
        role_code=role.code.value if role and hasattr(role.code, "value") else (role.code if role else ""),
        role_name=role.name if role else "—",
    )


def list_users(
    db: Session, tenant_id: int, *, query: str | None, status: str | None, limit: int, offset: int,
) -> tuple[list[User], int]:
    return UserRepository(db, tenant_id).search(query=query, status=status, limit=limit, offset=offset)


def get_user(db: Session, tenant_id: int, user_id: int) -> User:
    user = UserRepository(db, tenant_id).get(user_id)
    if user is None:
        raise NotFoundError("Usuário não encontrado.")
    return user


def create_user(
    db: Session, tenant_id: int, actor: User, payload: UserCreate, ip_address: str | None,
) -> User:
    enforce_user_limit(db, tenant_id)
    if get_user_by_email(db, payload.email) is not None:
        raise ConflictError("Já existe uma conta com este e-mail.")
    role = _role_or_400(db, payload.role_code)

    user = User(
        tenant_id=tenant_id, email=payload.email.strip().lower(), full_name=payload.full_name,
        phone=payload.phone, password_hash=hash_password(payload.password),
    )
    user.roles = [role]
    UserRepository(db, tenant_id).add(user)
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.CREATE, table_name="users",
        record_id=str(user.id), ip_address=ip_address, new_value={"email": user.email, "role": payload.role_code},
    )
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session, tenant_id: int, actor: User, user_id: int, payload: UserUpdate, ip_address: str | None,
) -> User:
    user = get_user(db, tenant_id, user_id)
    if user_id == actor.id and payload.status is not None and payload.status.value != "ATIVO":
        raise ValidationFailedError("Você não pode desativar ou bloquear a própria conta.")

    fields = payload.model_dump(exclude_unset=True, exclude={"role_code"})
    for field, value in fields.items():
        setattr(user, field, value)
    if payload.role_code is not None:
        user.roles = [_role_or_400(db, payload.role_code)]
    db.flush()

    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.UPDATE, table_name="users",
        record_id=str(user.id), ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    return user


def reset_password(
    db: Session, tenant_id: int, actor: User, user_id: int, payload: UserPasswordReset, ip_address: str | None,
) -> None:
    user = get_user(db, tenant_id, user_id)
    user.password_hash = hash_password(payload.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.flush()
    write_audit_log(
        db, tenant_id=tenant_id, user_id=actor.id, action=AuditAction.UPDATE, table_name="users",
        record_id=str(user.id), ip_address=ip_address, new_value={"password_reset": True},
    )
    db.commit()
