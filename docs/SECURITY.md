# Segurança — OpsFlow

Referência única do que já existe (espalhado pelo código desde as fases
iniciais) e do que foi adicionado na Fase 11 ("Hardening de segurança").
Nada aqui é aspiracional — cada item tem o arquivo/teste que garante que
ele é real.

## Autenticação e sessão

| Medida | Onde |
|---|---|
| Hash de senha com Argon2id | `app/core/security.py` |
| JWT de acesso de curta duração (15 min) + refresh token rotativo (7 dias) | `app/services/auth_service.py` |
| Refresh token armazenado só como hash, nunca em texto puro | `app/repositories/refresh_token_repository.py` |
| Bloqueio de conta após N tentativas de login erradas (padrão: 5, por 15 min) | `auth_service.login` |
| Mensagem de erro genérica em login (nunca revela se o e-mail existe) | `auth_service.login` |
| Sem "esqueci minha senha" self-service — decisão de produto, não lacuna técnica | ver `no-self-service-password-reset` — troca de senha é sempre uma ação do admin, tela Usuários |

## Isolamento multi-tenant

| Medida | Onde |
|---|---|
| Toda tabela de negócio tem `tenant_id`, FK real pra `tenants` | `test_tenant_isolation_schema.py` (guarda estática, roda a cada `pytest`) |
| Toda leitura/escrita de negócio passa por `TenantRepository` (filtro automático) | `app/repositories/base.py` |
| Ações de plataforma (`SUPER_ADMIN`) são a exceção documentada — `require_platform_admin` explicitamente exige `tenant_id IS NULL` | `app/api/deps.py` |

## RBAC

5 papéis fixos, permissões granulares (`recurso.ação`) por papel — nunca
checado só no desktop; toda rota sensível tem `Depends(require_permission(...))`
ou `Depends(require_platform_admin)` no backend. Um usuário de empresa
NUNCA alcança uma rota de `/platform/*`, não importa o papel — coberto por
`test_platform.py`.

## Auditoria

Toda ação sensível (criar/editar/excluir, mudança de status, login/logout,
backup/restore/arquivamento) grava uma linha em `audit_logs` — usuário, IP,
valor anterior/novo, quando aplicável. `app/services/audit_service.py`.

## API — Fase 11 (novo)

| Medida | Onde | Observação |
|---|---|---|
| Rate limiting (padrão: 120 req/min por IP) | `app/core/rate_limit.py` | `RATE_LIMIT_PER_MINUTE` no `.env`. Janela fixa, em memória — existia como configuração desde a Fase 1 mas nunca era de fato aplicado; corrigido agora. Desligado só pela suíte de testes (`RATE_LIMITING_ENABLED=false`). |
| `/docs`, `/redoc`, `/openapi.json` desligados fora de desenvolvimento | `Settings.docs_enabled` (`app_env != "production"`) | Publicar o contrato inteiro da API sem autenticação é um vazamento de informação desnecessário numa API real na internet. |
| Cabeçalhos de segurança em toda resposta | `app/core/security_headers.py` | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` restritiva. |
| CORS nunca combina `allow_origins=["*"]` com `allow_credentials=True` | `Settings.cors_allow_credentials` | Combinação que o próprio spec de CORS considera inválida. |
| `TrustedHostMiddleware` opcional | `ALLOWED_HOSTS` no `.env` (default `["*"]`, sem restrição) | Configure com o(s) domínio(s) reais antes de expor a API publicamente. |
| `/api/health` nunca vaza credencial do banco | `app/api/health.py::_database_host` (testado em `test_health.py`) | Mostra só `host:porta/banco`, nunca usuário/senha — mesmo sendo um endpoint sem autenticação nenhuma. |

## Backup/restore/arquivamento

- Nome de arquivo de backup validado por regex antes de qualquer operação de
  restore — impede um `filename` como `../../etc/passwd` virar leitura
  arbitrária de arquivo (`app/services/backup_service.py`).
- Senha do banco nunca passa por linha de comando (`mysqldump`/`mysql`) —
  sempre via variável de ambiente `MYSQL_PWD` do subprocesso, invisível pra
  qualquer outro processo que liste os argumentos deste.
- Backup/restore/arquivamento são exclusivos de `SUPER_ADMIN` — nunca uma
  ação de tenant.

## O que ainda depende do ambiente de implantação (fora do escopo do código)

- **HTTPS**: a API em si não termina TLS — isso é responsabilidade do
  proxy/load balancer na frente dela (nginx, Caddy, o próprio provedor de
  hospedagem). Nunca exponha a API em HTTP puro pra fora de uma rede
  confiável.
- **`JWT_SECRET`**: não tem valor padrão utilizável (`Field(default=...)`,
  obrigatório) — cada ambiente precisa gerar o seu (`Configurar
  Implantacao.bat`, botão "Gerar novo segredo").
- **Backups fora da máquina**: o robô de backup (`app/jobs/backup_job.py`)
  grava em disco local (`BACKUP_DIR`) — para proteção real contra perda de
  hardware, copie periodicamente esse diretório pra um armazenamento
  externo (não implementado; fora do escopo de código puro).
- **Atualização de dependências**: `requirements.txt` fixa versões, mas não
  há verificação automática de CVEs — rode `pip list --outdated` e revise o
  changelog de segurança de cada dependência periodicamente.
