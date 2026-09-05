"""Request/response schemas for `/api/v1/users` (seção 4/5) — gestão de
usuários dentro da própria empresa (ADMIN_EMPRESA convida/gerencia sua
equipe). `SUPER_ADMIN` nunca é um papel atribuível por aqui — é um usuário
de plataforma, fora do escopo de qualquer tenant (seção 54).
"""
from pydantic import BaseModel, Field

from app.models.enums import UserStatus
from app.schemas.auth import EmailAddress

ASSIGNABLE_ROLE_CODES = ("ADMIN_EMPRESA", "SUPERVISOR", "OPERADOR", "VISUALIZADOR")


class UserCreate(BaseModel):
    email: EmailAddress
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    role_code: str


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    status: UserStatus | None = None
    role_code: str | None = None


class UserPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=100)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    phone: str | None
    status: UserStatus
    role_code: str
    role_name: str
