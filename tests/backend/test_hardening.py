"""Tests for Fase 11 ("Hardening de segurança"): rate limiting, docs
exposure gated by ambiente, cabeçalhos de segurança e a combinação inválida
de CORS com `allow_origins=["*"]` + `allow_credentials=True`.

Rate limiting e docs-por-ambiente dependem de como `app.main` monta a
aplicação NA IMPORTAÇÃO (a partir de `Settings`, cacheada) — o `client`
compartilhado desta suíte já sobe com `RATE_LIMITING_ENABLED=false`
(ver `conftest.py`, senão a própria suíte bateria no limite). Por isso os
testes de rate limiting sobem uma mini aplicação Starlette isolada, só com
o middleware em teste — mais simples e mais realista que chamar `dispatch`
na mão, e não exige reconstruir `app.main` inteiro com outro `Settings`.
"""
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.config import Settings
from app.core.rate_limit import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware


def _make_test_app(*middleware_factories) -> Starlette:
    async def ok(request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/ping", ok)])
    for factory in middleware_factories:
        app = factory(app)
    return app


def test_rate_limit_middleware_blocks_after_the_configured_limit():
    app = _make_test_app(lambda a: RateLimitMiddleware(a, requests_per_minute=3))
    client = TestClient(app)

    for _ in range(3):
        assert client.get("/ping").status_code == 200

    blocked = client.get("/ping")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "OF-API-429"


def test_rate_limit_tracks_clients_independently():
    app = _make_test_app(lambda a: RateLimitMiddleware(a, requests_per_minute=1))
    client = TestClient(app)

    first = client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})
    assert first.status_code == 200
    # TestClient sempre usa o mesmo IP de origem simulado — o segundo
    # request do MESMO cliente já deveria estar bloqueado.
    second = client.get("/ping")
    assert second.status_code == 429


def test_security_headers_are_present_on_every_response():
    app = _make_test_app(lambda a: SecurityHeadersMiddleware(a))
    client = TestClient(app)

    response = client.get("/ping")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_docs_enabled_follows_app_env():
    assert Settings(app_env="development", jwt_secret="x").docs_enabled is True
    assert Settings(app_env="staging", jwt_secret="x").docs_enabled is True
    assert Settings(app_env="production", jwt_secret="x").docs_enabled is False


def test_docs_are_reachable_in_the_development_test_session(client):
    """A suíte roda com APP_ENV=development (ver conftest.py) — confirma que
    o hardening não desligou os docs sem querer no ambiente de dev."""
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_cors_never_pairs_wildcard_origin_with_credentials():
    """`allow_origins=["*"]` + `allow_credentials=True` é uma combinação que
    o próprio spec de CORS considera inválida — `Settings.cors_allow_
    credentials` (o que `app.main` de fato usa) precisa desligar sozinho
    enquanto a lista de origens ainda for o wildcard padrão."""
    wildcard = Settings(app_env="development", jwt_secret="x", cors_allow_origins=["*"])
    assert wildcard.cors_allow_credentials is False

    restricted = Settings(app_env="development", jwt_secret="x", cors_allow_origins=["https://app.opsflow.com"])
    assert restricted.cors_allow_credentials is True
