"""Cria (ou atualiza) um usuário avulso — utilitário de linha de comando para
uso enquanto a tela de Gestão de Usuários ainda não existe no desktop.

Idempotente: se o e-mail já existir, apenas atualiza senha/papel/nome em vez
de falhar — seguro rodar de novo.

Uso:
    python database/seeds/create_user.py --email x@y.com --password "..." \
        --name "Fulano de Tal" --role ADMIN_EMPRESA

`--role` aceita qualquer um dos 5 papéis fixos (seção 4): SUPER_ADMIN,
ADMIN_EMPRESA, SUPERVISOR, OPERADOR, VISUALIZADOR. Para todos exceto
SUPER_ADMIN, o usuário é vinculado à empresa demo (única existente hoje) —
SUPER_ADMIN não tem tenant (é um operador de plataforma, seção 54).
"""
import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import Role, Tenant, User  # noqa: E402
from app.models.enums import UserStatus  # noqa: E402


def create_or_update_user(
    db: Session, *, email: str, password: str, full_name: str, role_code: str,
) -> tuple[User, bool]:
    role = db.query(Role).filter(Role.code == role_code).one_or_none()
    if role is None:
        raise SystemExit(f"Papel {role_code!r} não existe. Use um dos 5 papéis fixos (seção 4).")

    tenant_id = None
    if role_code != "SUPER_ADMIN":
        tenant = db.query(Tenant).order_by(Tenant.id).first()
        if tenant is None:
            raise SystemExit("Nenhuma empresa cadastrada ainda — rode seed_demo.py primeiro.")
        tenant_id = tenant.id

    user = db.query(User).filter(User.email == email).one_or_none()
    created = user is None
    if user is None:
        user = User(email=email, full_name=full_name, tenant_id=tenant_id, status=UserStatus.ATIVO)
        db.add(user)

    user.password_hash = hash_password(password)
    user.full_name = full_name
    user.tenant_id = tenant_id
    user.status = UserStatus.ATIVO
    user.failed_login_attempts = 0
    user.locked_until = None
    user.roles = [role]
    db.flush()
    return user, created


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", required=True, dest="full_name")
    parser.add_argument(
        "--role", required=True, choices=["SUPER_ADMIN", "ADMIN_EMPRESA", "SUPERVISOR", "OPERADOR", "VISUALIZADOR"],
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user, created = create_or_update_user(
            db, email=args.email, password=args.password, full_name=args.full_name, role_code=args.role,
        )
        db.commit()
        action = "criado" if created else "atualizado"
        print(f"[create_user] Usuário {action}: {user.email} (id={user.id}, papel={args.role}).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
