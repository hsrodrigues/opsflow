"""Security response headers (Fase 11 "Hardening de segurança").

Um punhado de cabeçalhos padrão que não custam nada e fecham classes
inteiras de ataque contra o pouco de superfície HTML que esta API tem
(`/docs`, `/redoc`, e qualquer resposta de erro renderizada num navegador
por engano) — a maior parte do tráfego real é o desktop (PySide6) via
`httpx`, que nem interpreta estes cabeçalhos, mas eles são de graça e
protegem qualquer acesso feito por um navegador.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        return response
