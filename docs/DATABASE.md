# Banco de dados — OpsFlow

29 tabelas, MySQL 8+ em produção. A fonte de verdade do schema é sempre o
ORM (`backend/app/models/`); a migration em
`database/migrations/versions/0001_initial_schema.py` foi gerada a partir
dele via `alembic revision --autogenerate` e nunca deve divergir — qualquer
mudança de schema é feita primeiro no modelo, depois numa nova migration
gerada da mesma forma.

## Convenções

- **PK**: `id BIGINT AUTO_INCREMENT` em toda tabela (exceto as tabelas de
  associação pura, com chave composta). Ver `app/models/types.bigint_pk()`.
- **`tenant_id`**: presente em toda tabela de dado de negócio (`TenantMixin`),
  `FOREIGN KEY → tenants.id ON DELETE CASCADE`, sempre indexado. Garantido
  por `tests/backend/test_tenant_isolation_schema.py`.
- **Timestamps**: `created_at`/`updated_at` (`TimestampMixin`) gerenciados
  pelo banco (`server_default`/`onupdate`).
- **Auditoria de registro**: `created_by`/`updated_by` (`AuditMixin`) → `users.id`.
- **Soft delete**: `deleted_at` nullable (`SoftDeleteMixin`) nas tabelas onde
  exclusão não pode ser física (veículos, motoristas, transportadoras, rotas,
  programação, ocorrências).
- **Enums**: armazenados como `VARCHAR`, não `ENUM` nativo do MySQL
  (`app/models/types.enum_column()`) — permite adicionar um novo valor sem
  `ALTER TABLE` e mantém o schema portável para os testes em SQLite.

## Tabelas de referência do sistema (não pertencem a um tenant)

| Tabela | Descrição |
|---|---|
| `plans` | Catálogo comercial (STARTER/PROFESSIONAL/BUSINESS/ENTERPRISE — seção 7), com `max_users`/`max_vehicles` (`NULL` = ilimitado) e `features` (JSON). Seedado na migration inicial. |
| `roles` | Os 5 papéis fixos do RBAC (seção 4). Seedado na migration inicial. |
| `permissions` | Ações granulares (`recurso.ação`, ex. `vehicles.manage`). Seedado na migration inicial. |
| `role_permissions` | Associação N:N `roles`↔`permissions`. |

## Tenant, licenciamento e RBAC por empresa

| Tabela | Descrição |
|---|---|
| `tenants` | A empresa cliente. Raiz do isolamento multi-tenant. |
| `subscriptions` | Registro comercial/billing: qual plano, desde quando, período atual. |
| `licenses` | Registro de **enforcement**, validado pela API a cada login: `status` (ACTIVE/TRIAL/SUSPENDED/EXPIRED/CANCELLED), `expires_at`, limites que podem sobrescrever o plano. Separado de `subscriptions` para uma futura integração de pagamento (`PaymentProvider`, seção 55) não tocar a lógica de enforcement. |
| `users` | `tenant_id` **nullable** — só é `NULL` para `SUPER_ADMIN` (usuário de plataforma, seção 54), nunca para os demais papéis. |
| `user_roles` | Associação N:N `users`↔`roles`, com `tenant_id` denormalizado para reforçar isolamento em auditorias de atribuição de papel. |
| `refresh_tokens` | Uma linha por sessão ativa; só o hash do token é armazenado. |
| `password_reset_tokens` | Token de uso único do fluxo "esqueci minha senha". |

## Cadastros operacionais

| Tabela | Descrição |
|---|---|
| `carriers` | Transportadoras (seção 11). |
| `vehicle_types` | Classificação de veículo configurável por tenant. |
| `vehicles` | Veículos (seção 9); `current_driver_id` aponta o motorista atual. |
| `drivers` | Motoristas (seção 10); `cnh_expiry` alimenta os alertas de vencimento. |
| `locations` | Pontos nomeados (origem/destino), com lat/long opcional — pronta para integração de mapas (seção 22) sem mudança de schema. |
| `routes` | Rotas origem→destino (seção 12). |

## Programação e execução operacional (seção 13/21)

A especificação lista `operations`, `schedules` e `schedule_items` como
tabelas distintas; a sobreposição conceitual entre "o que foi programado" e
"o que está acontecendo agora" é resolvida assim:

```
Schedule (cabeçalho: data + turno)
   └─ ScheduleItem (uma viagem planejada: rota, transportadora,
      veículo, motorista, horário previsto, carga, quantidade)
        └─ Operation (criada quando o item sai de PROGRAMADO;
           é o registro "ao vivo" exibido no Centro de Operações,
           carrega o operation_number visível na UI, ex. "10231")
             └─ StatusHistory (uma linha por transição de status —
                a timeline da seção 13)
```

| Tabela | Descrição |
|---|---|
| `schedules` | Cabeçalho por data + turno. |
| `schedule_items` | Uma viagem planejada. `status`: `PROGRAMADO → AGUARDANDO → EM_FILA → EM_OPERACAO → CONCLUIDO` (ou `ATRASADO`/`CANCELADO`). |
| `operations` | Instância de execução de um `schedule_item` (`UNIQUE(schedule_item_id)`). Reusa o mesmo enum de status. |
| `status_history` | Timeline de mudanças de status de uma `operation`. |

## Ocorrências, notificações e auditoria

| Tabela | Descrição |
|---|---|
| `occurrence_types` | Categoria configurável por tenant (atraso, quebra, acidente, ...). |
| `occurrences` | Ocorrência (seção 14): `severity` (BAIXA/MEDIA/ALTA/CRITICA), `status` (ABERTA/EM_ANALISE/RESOLVIDA/CANCELADA), ligada opcionalmente a uma `operation`/`vehicle`/`driver`. |
| `attachments` | Arquivo anexado a uma ocorrência (único caso de anexo no MVP). |
| `notifications` | `user_id NULL` = broadcast para todo o tenant. |
| `audit_logs` | Trilha de auditoria (seção 19): `tenant_id` nullable (ações de `SUPER_ADMIN` não pertencem a um tenant), valor anterior/novo em JSON. |

## Configuração e integrações

| Tabela | Descrição |
|---|---|
| `system_settings` | Chave/valor (JSON); `tenant_id NULL` = default de plataforma, sobrescrito por uma linha com o mesmo `key` e `tenant_id` preenchido. |
| `api_keys` | Credencial de integração; só o hash é armazenado. |
| `integration_configs` | Configuração por tipo de integração (SAP, Power BI, WhatsApp, e-mail, GPS, TMS, WMS, ERP — seção 41). Nenhum adapter é implementado na Fase 1 — a tabela só prepara o schema. `config` deve ser cifrado em repouso quando um adapter real existir (ver `docs/SECURITY.md`, fase de hardening). |

## Rodando as migrations

```bash
# a partir da raiz do projeto, com o venv ativado
alembic -c database/migrations/alembic.ini upgrade head    # aplica
alembic -c database/migrations/alembic.ini downgrade base  # reverte tudo
alembic -c database/migrations/alembic.ini revision --autogenerate -m "..."  # nova migration
```

A URL de conexão vem sempre de `DATABASE_URL` (`.env`/ambiente) — nunca de
um valor commitado em `alembic.ini`.
