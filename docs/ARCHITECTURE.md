# Arquitetura — OpsFlow

## Visão geral

```
                    INTERNET
                       │
                       ▼
              ┌─────────────────┐
              │   API BACKEND   │
              │    FastAPI      │
              └────────┬────────┘
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
       ┌────────────┐      ┌─────────────┐
       │   MySQL    │      │ Redis       │
       │  Database  │      │ Cache/Jobs  │
       └────────────┘      └─────────────┘
             ▲
             │ HTTPS
       ┌─────┴──────┐
       │  OpsFlow   │
       │ Desktop    │
       │  PySide6   │
       └────────────┘
```

| Camada | Tecnologia | Decisão |
|---|---|---|
| Desktop | Python + PySide6 | Fase 8 |
| Backend | Python + FastAPI | SQLAlchemy 2.x **síncrono** (FastAPI roda handlers em threadpool; evita a complexidade de um driver MySQL assíncrono sem necessidade real no MVP) |
| ORM | SQLAlchemy 2.x | `Mapped`/`mapped_column`, ver `backend/app/models/` |
| Banco | MySQL 8+ | Produção. SQLite é usado **apenas** em testes automatizados (ver `tests/backend/conftest.py`) |
| Validação | Pydantic v2 | Schemas de request/response (Fase 2+) |
| Autenticação | JWT (access + refresh) | `PyJWT`, hash de senha com **Argon2id** (`argon2-cffi`) — ver `app/core/security.py` |
| Jobs | APScheduler / Celery+Redis | Introduzido quando a primeira automação realmente precisar (não incluído na Fase 1) |
| Logs | `logging` + rotação | `app/core/logging_config.py`: `logs/application.log`, `logs/errors.log`, `logs/audit.log` |
| Empacotamento | PyInstaller + Inno Setup | Fases 8/10 |
| Containers | Docker Compose (dev) | `docker/docker-compose.yml`: `api` + `mysql` + `redis` |

## Princípio fundamental: multi-tenant

Uma instalação atende várias empresas (`tenants`). Toda tabela de dado de
negócio carrega `tenant_id` (via `TenantMixin`, `app/models/base.py`) e
**toda** query de negócio deve ser filtrada pelo tenant autenticado — a
partir da Fase 2, essa filtragem é centralizada na camada de Repository, não
deixada a cargo de cada endpoint. `tests/backend/test_tenant_isolation_schema.py`
é uma guarda automática que falha se alguém adicionar uma tabela de negócio
sem `tenant_id`.

## Camadas do backend

```
backend/app/
├── api/          # HTTP: routers FastAPI, validação de entrada, serialização
├── core/         # config, database, logging, exceptions, security — infraestrutura
├── models/       # SQLAlchemy ORM — a fonte de verdade do schema
├── repositories/ # acesso a dado, sempre filtrado por tenant_id (Fase 2+)
├── schemas/      # Pydantic — contratos de request/response (Fase 2+)
└── services/     # regras de negócio, orquestração (Fase 2+)
```

Fluxo de uma requisição (a partir da Fase 2): `api` valida e desserializa →
`service` aplica regra de negócio → `repository` consulta/persiste (sempre
com `tenant_id`) → `service` monta a resposta → `api` serializa. Nenhuma
camada pula a anterior.

## RBAC

5 papéis fixos (`SUPER_ADMIN`, `ADMIN_EMPRESA`, `SUPERVISOR`, `OPERADOR`,
`VISUALIZADOR`), seedados como dado de referência na migration inicial
(`database/migrations/versions/0001_initial_schema.py`), junto de uma
matriz de permissões granulares (`recurso.ação`, ex. `vehicles.manage`). O
enforcement por endpoint chega na Fase 2.

## Fluxo de autenticação (seção 5)

```
POST /auth/login {email, senha}
  → busca usuário, confere locked_until, verifica hash Argon2
  → falha → incrementa failed_login_attempts; bloqueia após
    max_login_attempts (5) por login_lockout_minutes (15)
  → sucesso → checa status do tenant/licença → emite access_token
    (15 min) + refresh_token (7 dias, hash persistido em refresh_tokens)

POST /auth/refresh {refresh_token}
  → valida hash, não revogado, não expirado → rotaciona (revoga o antigo,
    emite novo par) — mitiga replay

POST /auth/logout
  → revoga o refresh_token da sessão atual
```

## Fluxo de licenciamento (seção 6)

```
Login OK → API retorna status da licença do tenant junto do token
  EXPIRED/SUSPENDED/CANCELLED → bloqueia telas de negócio, permite só
    a tela de licença (para ADMIN_EMPRESA renovar)
  TRIAL → banner de contagem regressiva até expires_at
Toda criação (usuário, veículo) verifica no service layer:
  count atual < max_users/max_vehicles do plano (ou override em licenses)
  → excede → 402 OF-API-402 "limite do plano atingido"
```

`license_key` é um identificador público, nunca um segredo: a validação é
sempre feita server-side contra `status`/`expires_at`/limites.

## Tratamento de erros

Toda exceção de domínio herda `OpsFlowError` (`app/core/exceptions.py`) e
carrega um `error_code` estável (`OF-API-xxx`) e uma `friendly_message` em
português — o handler global nunca expõe detalhe técnico ao cliente, só ao
log (`logs/errors.log`).

## Ambiente e segredos

Configuração via variáveis de ambiente (`app/core/config.py`, Pydantic
Settings) carregadas de um `.env` **nunca versionado** — `.env.example`
documenta cada variável sem valores reais. `JWT_SECRET` não tem valor padrão
utilizável em produção (deve ser sempre sobrescrito).

## Ambiente de desenvolvimento local sem Docker

Quando Docker/MySQL não estão disponíveis, `DATABASE_URL` pode apontar para
um arquivo SQLite (`sqlite:///./opsflow_dev.db`) — todo o schema (colunas,
enums, JSON) foi desenhado para ser válido nos dois dialetos (ver
`app/models/types.py`). Isso nunca é usado em produção; a migration é
adicionalmente validada em modo offline contra o dialeto MySQL
(`alembic upgrade head --sql`) antes de cada entrega.
