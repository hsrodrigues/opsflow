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

Uma licença **já ativada** (com `tenant_id` preenchido) usa `license_key`
como identificador público — a validação de acesso é sempre feita
server-side contra `status`/`expires_at`/limites, nunca a própria chave.

### Ativação por chave solta (autoatendimento)

Uma licença **ainda não ativada** é a exceção a essa regra: enquanto
`tenant_id IS NULL`, conhecer a `license_key` **é** a autorização — o
mesmo modelo de confiança de um token de redefinição de senha. Fluxo:

```
SUPER_ADMIN (Console de Plataforma, "Gerar chave")
  → POST /platform/license-keys {plan_code, trial_days}
  → cria uma License solta: tenant_id=NULL, pending_trial_days, sem mais nada
  → SUPER_ADMIN copia a chave e repassa ao cliente por fora (WhatsApp, e-mail)

Cliente (tela de login, "Recebeu uma chave de ativação? Ative aqui")
  → POST /api/v1/activation/activate {license_key, dados da empresa, admin}
  → ÚNICO endpoint não-autenticado da API que muda dado, de propósito
  → rejeita se a chave não existir (422) ou já tiver sido usada (409)
  → cria Tenant + primeiro usuário ADMIN_EMPRESA + finaliza a License
    (tenant_id, status=TRIAL, activated_at=agora,
     expires_at = agora + pending_trial_days — o relógio do trial começa
     na ATIVAÇÃO, não na geração da chave)
  → devolve um TokenResponse completo: o cliente sai logado, sem precisar
    de um passo de login separado
```

Por isso o backend do Console de Plataforma e o app do cliente **precisam
apontar para o mesmo servidor** — a chave só existe nesse banco
compartilhado; não há validação local nem por hardware.

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

## Jobs em background (app/jobs/)

Adiantado da seção 41 ("Automações", V2 no roadmap original) porque o valor
era claro e a infraestrutura já estava reservada na arquitetura
(APScheduler, seção 2). São funções `run()` simples, cada uma abrindo sua
própria sessão de banco (`SessionLocal()` — nunca a sessão de uma request) e
varrendo *todos* os tenants ativos, registradas no `BackgroundScheduler` do
APScheduler e iniciadas/paradas junto do ciclo de vida do FastAPI
(`app/main.py`). Rodam dentro do próprio processo da API — não precisam de
Celery/Redis para o volume esperado do MVP.

- **`delay_detection`** (a cada 5 min): `schedule_item`s ainda ativos cujo
  horário previsto + tempo estimado da rota já passou viram `ATRASADO`
  automaticamente, reaproveitando `schedule_service.change_status` (que
  aceita `actor_id=None` para uma mudança de status iniciada pelo sistema).
- **`cnh_alerts`** (a cada 24h): motoristas com CNH vencendo em até 30 dias
  (`DriverRepository.expiring_cnh`) geram uma notificação por destinatário,
  com deduplicação de 24h (`NotificationRepository.recently_notified`) para
  não reenviar o mesmo aviso a cada execução.
- **`license_expiration`** (a cada 60 min): licenças `ACTIVE`/`TRIAL` cujo
  `expires_at` já passou viram `EXPIRED` automaticamente.
- **`backup_job`** (a cada 24h, configurável): roda `mysqldump` de verdade
  contra o banco inteiro (todos os tenants — não dá pra recortar um dump por
  `tenant_id`) e grava em `BACKUP_DIR`, podando os mais antigos além de
  `BACKUP_RETENTION_COUNT`. Diferente dos outros três, não abre
  `SessionLocal()` nem varre tenants — fala com o MySQL via subprocess, não
  via SQLAlchemy (`app/services/backup_service.py`). Geração sob demanda e
  restauração ficam atrás de `/api/v1/platform/backups`, exclusivo de
  `SUPER_ADMIN`.

  **Cautela ao restaurar durante um request vivo**: `restore_backup`
  reexecuta o dump inteiro (`DROP TABLE`/`CREATE TABLE` em cada tabela,
  `users` incluída). Se o handler HTTP que chama isso ainda estiver com a
  própria transação SQLAlchemy aberta (o padrão do `get_db`: só fecha no fim
  do request) tendo lido `users` momentos antes — caso do próprio
  `require_platform_admin` — o MySQL bloqueia o `DROP TABLE` externo
  esperando o metadata lock que essa transação segura, e essa transação só
  terminaria quando o PRÓPRIO request acabasse: autodeadlock. Reproduzido de
  verdade contra o MySQL de dev; a correção é sempre dar `db.commit()`
  explícito bem antes de chamar `restore_backup`, liberando esse lock antes
  do subprocess rodar (ver `app/api/v1/platform.py`).

Cada job notifica os usuários `ADMIN_EMPRESA`/`SUPERVISOR` do tenant
afetado (`app/jobs/recipients.py`) — exceto o `backup_job`, que não é por
tenant. `JOBS_ENABLED=false` desliga o
scheduler inteiro — usado pela suíte de testes (`tests/backend/conftest.py`)
para nunca ter uma thread em background competindo com o banco de teste;
os jobs em si são testados chamando `run()` diretamente
(`tests/backend/test_jobs.py`).

### Automação síncrona (não é um job)

Nem toda automação precisa esperar a próxima varredura periódica. Registrar
uma ocorrência do tipo "Acidente" contra um veículo bloqueia esse veículo
(`vehicles.status = BLOQUEADO`) e notifica `ADMIN_EMPRESA`/`SUPERVISOR` na
**mesma transação** da criação da ocorrência (`occurrence_service.
_auto_block_vehicle_on_accident`) — instantâneo, não up-to-5-minutos-depois
como os jobs acima, e atômico: nunca existe um acidente registrado sem o
veículo bloqueado, ou vice-versa. Reaproveita `recipients_for_tenant` e
`notification_service.create_notification`, os mesmos helpers dos jobs em
background.

## Ambiente de desenvolvimento local

O ambiente de desenvolvimento roda contra um MySQL 8 real, instalação
standalone via MySQL Installer (`DATABASE_URL=mysql+pymysql://root:<senha>@
127.0.0.1:3306/opsflow_db`). Um MySQL/MariaDB via XAMPP foi usado
anteriormente, mas teve corrupção irrecuperável nas tabelas internas do
MariaDB (engine Aria) — trocado pela instalação standalone. Quando Docker/
MySQL não estão disponíveis, `DATABASE_URL` também pode apontar para um
arquivo SQLite (`sqlite:///./opsflow_dev.db`) — todo o schema (colunas,
enums, JSON) foi desenhado para ser válido nos dois dialetos (ver
`app/models/types.py`), mas cada migration autogerada ainda precisa ser
revisada à mão antes de commitar (ver a nota correspondente em
`docs/DATABASE.md`) — o autogenerate roda contra o banco de desenvolvimento
configurado (MySQL) e pode emitir sintaxe que só esse dialeto entende. Os
testes automatizados (`tests/backend/`) sempre usam SQLite isolado por
design, independentemente do banco de desenvolvimento configurado — mantém
a suíte rápida e sem efeito colateral no banco "de verdade", e funciona
como a verificação real de portabilidade de cada migration nova.
