"""`/api/v1/auth` — login, refresh, logout, current-user (seção 5/23)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.auth import LoginRequest, LogoutRequest, MyProfileUpdate, RefreshRequest, TokenResponse, UserInfo
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    return auth_service.login(
        db, email=payload.email, password=payload.password, remember=payload.remember,
        ip_address=_client_ip(request), user_agent=request.headers.get("user-agent"),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    return auth_service.refresh(
        db, raw_refresh_token=payload.refresh_token, ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/logout", status_code=204)
def logout(payload: LogoutRequest, request: Request, db: Session = Depends(get_db)) -> None:
    auth_service.logout(db, raw_refresh_token=payload.refresh_token, ip_address=_client_ip(request))


@router.get("/me", response_model=UserInfo)
def me(current_user=Depends(get_current_user)) -> UserInfo:
    return auth_service.build_user_info(current_user)


@router.patch("/me", response_model=UserInfo)
def update_me(
    payload: MyProfileUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db),
) -> UserInfo:
    return auth_service.update_own_profile(db, current_user, payload)
