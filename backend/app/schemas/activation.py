"""Schema for `/api/v1/activation/activate` — a prospective customer
redeeming a `license_key` a `SUPER_ADMIN` generated for them (seção 6). The
only pre-auth, unauthenticated endpoint in the API that creates data on
purpose: knowing a valid, unclaimed key *is* the authorization, the same
trust model as `password_reset_tokens` — a single-use secret, not a login.
"""
from pydantic import BaseModel, Field

from app.schemas.auth import EmailAddress


class ActivationRequest(BaseModel):
    license_key: str = Field(min_length=1, max_length=64)
    legal_name: str = Field(min_length=1, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    cnpj: str | None = Field(default=None, max_length=18)
    admin_full_name: str = Field(min_length=1, max_length=200)
    admin_email: EmailAddress
    admin_password: str = Field(min_length=8, max_length=100)
