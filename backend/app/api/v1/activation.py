"""`/api/v1/activation` — o único endpoint da API sem autenticação de
propósito: um prospect sem conta nenhuma resgatando uma `license_key` que
um `SUPER_ADMIN` gerou pra ele (seção 6). Conhecer uma chave válida e ainda
não usada *é* a autorização, o mesmo modelo de confiança de um token de
reset de senha — não uma sessão.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.activation import ActivationRequest
from app.schemas.auth import TokenResponse
from app.services import activation_service

router = APIRouter(prefix="/activation", tags=["activation"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/activate", response_model=TokenResponse)
def activate(payload: ActivationRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    return activation_service.activate_license_key(
        db, payload, _client_ip(request), request.headers.get("user-agent"),
    )
