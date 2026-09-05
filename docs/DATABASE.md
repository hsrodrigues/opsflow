# Banco de dados — OpsFlow

34 tabelas, MySQL 8+ em produção. A fonte de verdade do schema é sempre o
ORM (`backend/app/models/`); cada migration em
`database/migrations/versions/` foi gerada a partir dele via `alembic
revision --autogenerate` e nunca deve divergir — qualquer mudança de schema
é feita primeiro no modelo, depois numa nova migration gerada da mesma
forma. Uma migration autogerada apontando para MySQL pode emitir sintaxe
específica do dialeto (ex. `server_default=sa.text('now()')`, ou um
`ALTER TABLE ... ADD CONSTRAINT` direto) que quebra ao rodar contra o
SQLite dos testes — sempre revisar o arquivo gerado antes de commitar (ver
`..._products.py` para os dois ajustes reais que isso exigiu: trocar
`now()` por `(CURRENT_TIMESTAMP)`, e envolver a alteração de
`schedule_items` em `op.batch_alter_table(...)`).

A migration de `..._stored_procedures_and_archive_tables.py` foi além
disso: **stored procedures** (`CREATE PROCEDURE`, cursor, `SIGNAL`) não
existem em SQLite de jeito nenhum, não é uma questão de sintaxe divergente
— por isso ficam atrás de um guard explícito (`if op.get_bind().dialect.
name == "mysql":`), enquanto as 4 tabelas de arquivo que as procedures
usam continuam portáveis (geradas normalmente por autogenerate, sem SQL
cru). A lógica de negócio de cada procedure também existe em Python puro
(dialeto ≠ MySQL cai num fallback via ORM) — ver `docs/ARCHITECTURE.md`.

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
| `licenses` | Registro de **enforcement**, validado pela API a cada login: `status` (ACTIVE/TRIAL/SUSPENDED/EXPIRED/CANCELLED), `expires_at`, limites que podem sobrescrever o plano. Separado de `subscriptions` para uma futura integração de pagamento (`PaymentProvider`, seção 55) não tocar a lógica de enforcement. `tenant_id` **nullable**: uma linha pode existir sem empresa nenhuma ainda — uma chave gerada por `SUPER_ADMIN` (`plan_code` + `pending_trial_days`, sem mais nada) esperando ser resgatada em `POST /api/v1/activation/activate`, o único endpoint não-autenticado da API por design (conhecer a chave É a autorização). `activated_at` marca o resgate; o relógio do trial começa aí, não na geração. |
| `users` | `tenant_id` **nullable** — só é `NULL` para `SUPER_ADMIN` (usuário de plataforma, seção 54), nunca para os demais papéis. |
| `user_roles` | Associação N:N `users`↔`roles`, com `tenant_id` denormalizado para reforçar isolamento em auditorias de atribuição de papel. |
| `refresh_tokens` | Uma linha por sessão ativa; só o hash do token é armazenado. |
| `password_reset_tokens` | Existe no schema desde a Fase 1, mas **nunca é escrita nem lida por nenhum fluxo** — decisão deliberada de produto (não técnica): OpsFlow não tem "esqueci minha senha" self-service; qualquer troca de senha é sempre uma ação do admin da empresa, editando o usuário na tela Usuários (`PATCH /users/{id}/reset-password`). Mantida no schema só para não quebrar a migration inicial; não estenda esta tabela para reviver esse fluxo sem confirmar com o cliente antes. |

## Cadastros operacionais

| Tabela | Descrição |
|---|---|
| `carriers` | Transportadoras (seção 11). |
| `vehicle_types` | Classificação de veículo configurável por tenant. |
| `vehicles` | Veículos (seção 9); `current_driver_id` aponta o motorista atual. |
| `drivers` | Motoristas (seção 10); `cnh_expiry` alimenta os alertas de vencimento. |
| `locations` | Pontos nomeados (origem/destino), com lat/long opcional — pronta para integração de mapas (seção 22) sem mudança de schema. |
| `routes` | Rotas origem→destino (seção 12). |
| `products` | Catálogo do que é transportado — fora do escopo original da seção 8, adicionado para tirar a ambiguidade de `schedule_items.quantity` (antes um número sem unidade declarada em lugar nenhum da UI). Cada produto declara sua própria `unit_of_measure` (UNIDADE/KG/TONELADA/LITRO/CAIXA/PALETE/METRO_CUBICO). |

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
| `schedule_items` | Uma viagem planejada. `status`: `PROGRAMADO → AGUARDANDO → EM_FILA → EM_OPERACAO → CONCLUIDO` (ou `ATRASADO`/`CANCELADO`). `product_id` (opcional, `ON DELETE SET NULL`) referencia `products` — a unidade exibida na Programação vem do produto, não é digitada de novo. Só pode ser excluída (`DELETE`) enquanto ainda está em `PROGRAMADO`; depois disso carrega histórico operacional de verdade e o caminho é mudar o status para `CANCELADO`. |
| `operations` | Instância de execução de um `schedule_item` (`UNIQUE(schedule_item_id)`). Reusa o mesmo enum de status. Delegado pra `sp_close_stale_operations` (procedure) fechar automaticamente as que ficam paradas demais num status intermediário — ver `docs/ARCHITECTURE.md`. |
| `status_history` | Timeline de mudanças de status de uma `operation`. |

## Arquivo (dados antigos movidos das tabelas acima)

Espelham as colunas de `operations`/`schedule_items`/`status_history`/
`occurrences`, mais um `archived_at` — sem relationship nem FK de volta pras
tabelas de origem (deliberado: são registros históricos passivos, e uma FK
ali ficaria bloqueada pela própria tabela que o arquivamento está
esvaziando). `tenant_id` mantém FK real pra `tenants` (a guarda estática de
isolamento multi-tenant exige isso de toda tabela com `tenant_id`, e é
seguro aqui — arquivar nunca mexe em `tenants`). Populadas por
`sp_archive_old_records` (MySQL) ou pelo fallback ORM equivalente
(`app/services/archive_service.py`), disparado sob demanda pelo Console de
Plataforma — nunca automaticamente, ao contrário dos robôs de `app/jobs/`
(decidir QUANDO arquivar é do operador da plataforma, não silencioso).

| Tabela | Descrição |
|---|---|
| `operations_archive` | Cópia de `operations` concluídas/canceladas há mais de N meses, sem nenhuma `occurrence` ainda vinculada. |
| `schedule_items_archive` | O `schedule_item` correspondente a cada `operation` arquivada. |
| `status_history_archive` | A timeline de cada `operation` arquivada (o detalhe passo-a-passo não é preservado se a operação nunca for arquivada — só existe aqui, nunca é copiado sem a operação também ser). |
| `occurrences_archive` | Cópia de `occurrences` resolvidas/canceladas há mais de N meses, sem nenhum `attachment` (arquivar perderia o anexo sem deixar rastro — por enquanto essas ficam de fora). |

## Ocorrências, notificações e auditoria

| Tabela | Descrição |
|---|---|
| `occurrence_types` | Categoria configurável por tenant (atraso, quebra, acidente, ...). |
| `occurrences` | Ocorrência (seção 14): `severity` (BAIXA/MEDIA/ALTA/CRITICA), `status` (ABERTA/EM_ANALISE/RESOLVIDA/CANCELADA), ligada opcionalmente a uma `operation`/`vehicle`/`driver`. Criar uma ocorrência do tipo "Acidente" contra um veículo bloqueia esse veículo (`vehicles.status = BLOQUEADO`) na mesma transação e notifica `ADMIN_EMPRESA`/`SUPERVISOR` — automação síncrona em `occurrence_service.py`, não um job em background. |
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
