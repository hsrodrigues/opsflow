"""`/api/v1/panel` — painel de operações somente-leitura para TV.

`GET /panel/{token}/board` é **público de propósito**: uma TV do centro de
operações não faz login. A segurança vem da posse de um token opaco e longo
(38+ chars, `secrets.token_urlsafe`), não adivinhável — o mesmo modelo de um
link de compartilhamento. Os outros dois endpoints (emitir/renovar o token)
exigem sessão normal e `settings.manage`, e nunca aceitam um token vindo do
cliente — só o backend gera.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant_id, require_permission
from app.core.database import get_db
from app.models.user import User
from app.schemas.panel import PanelBoardOut, PanelTokenOut
from app.services import panel_service

router = APIRouter(prefix="/panel", tags=["panel"])


def _token_out(token: str) -> PanelTokenOut:
    return PanelTokenOut(token=token, board_path=f"/painel/{token}")


@router.get("/token", response_model=PanelTokenOut)
def get_panel_token(
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("settings.manage")),
    db: Session = Depends(get_db),
) -> PanelTokenOut:
    return _token_out(panel_service.get_or_create_panel_token(db, tenant_id))


@router.post("/token/regenerate", response_model=PanelTokenOut)
def regenerate_panel_token(
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_permission("settings.manage")),
    db: Session = Depends(get_db),
) -> PanelTokenOut:
    return _token_out(panel_service.regenerate_panel_token(db, tenant_id))


@router.get("/{token}/board", response_model=PanelBoardOut)
def get_panel_board(token: str, db: Session = Depends(get_db)) -> PanelBoardOut:
    tenant = panel_service.resolve_tenant_by_token(db, token)
    return panel_service.get_board(db, tenant)
