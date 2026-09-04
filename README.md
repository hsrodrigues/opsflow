# OpsFlow

**Gestão Operacional Inteligente**

Plataforma SaaS/desktop multi-tenant de gestão operacional e logística —
para empresas que hoje controlam sua operação em planilhas, WhatsApp e
processos manuais. Cadastro de veículos, motoristas e transportadoras,
programação operacional, ocorrências, dashboards, relatórios, auditoria e
licenciamento comercial.

> **Status:** em desenvolvimento por fases. Este README reflete o que está
> implementado agora e é atualizado ao final de cada fase — ver
> [Roadmap](#roadmap) abaixo para o que ainda falta.

## Features

Implementado até agora:

**Fase 1 — Arquitetura**
- Schema completo do banco (29 tabelas) com isolamento multi-tenant por
  `tenant_id`, RBAC com 5 papéis e matriz de permissões, catálogo de planos.
- API FastAPI com tratamento de erro global, health check e logging
  estruturado com rotação.
- Migrations Alembic e seed de dados demonstrativos.

**Fase 2 — Autenticação (backend + fatia mínima do desktop)**
- Login/refresh/logout com JWT + refresh token rotativo, bloqueio por
  tentativas excessivas, RBAC (`get_current_user`/`require_permission`).
- Desktop: tela de login (seção 5) e shell principal navegável (sidebar,
  topbar, tema claro/escuro, indicador de conexão) — adiantados da Fase 8
  para permitir validação visual desde já.

**Fase 3 — Cadastros (concluída)**
- CRUD completo de Transportadoras, Motoristas, Veículos e Rotas: busca,
  filtros, paginação, validação de duplicidade (CNPJ/CPF/placa), soft
  delete, enforcement do limite de veículos do plano (seção 6), trilha de
  auditoria. Rotas resolve Origem/Destino para `locations` reaproveitáveis
  (find-or-create), já pronto para a integração de mapas da seção 22.
- Desktop: as 4 telas de cadastro completas — busca, filtro por status,
  paginação, criar/editar (diálogo modal)/excluir com confirmação — com
  visual padronizado (badges de status, alerta de CNH vencendo).
- Desktop: máscara de entrada ao vivo para CPF/CNPJ/telefone.

**Fase 4 — Operações (concluída)**
- Programação operacional (seção 13): cria uma programação (rota,
  transportadora, veículo, motorista, horário previsto, carga); o primeiro
  registro de status fora de `PROGRAMADO` gera automaticamente a `Operation`
  (com `operation_number`) e cada mudança subsequente grava uma linha na
  timeline (`status_history`).
- Centro de Operações (seção 21): contadores (Programadas/Em operação/
  Atrasadas) e quadro ao vivo das operações ativas, com atualização
  automática a cada 15s.
- Desktop: telas de Programação (criar, filtrar por data/status, alterar
  status com linha do tempo) e Centro de Operações (mesmo visual do mockup
  da especificação — cartões + tabela com badges coloridos).

**Notificações e automações (adiantado da seção 41, "Robôs")**
- Notificações (seção 20): `/api/v1/notifications`, cada usuário vê as suas
  + os avisos de toda a empresa.
- 3 jobs em background (APScheduler, `app/jobs/`), rodando dentro do próprio
  processo da API: detecção automática de atraso (compara horário previsto
  + tempo estimado da rota com agora), alerta de CNH vencendo (seção 10) e
  expiração automática de licença (seção 6) — todos notificam
  automaticamente os administradores/supervisores da empresa, sem depender
  de alguém abrir uma tela para "descobrir" o problema.

Planejado, fase a fase — ver [ARCHITECTURE.md](docs/ARCHITECTURE.md) e a
seção [Roadmap](#roadmap).

## Arquitetura

```
Desktop (PySide6)  --HTTPS/JWT-->  API (FastAPI)  -->  MySQL 8 (SQLAlchemy 2.x)
                                         |
                                         +--> Redis (cache/jobs)
```

Detalhes completos, modelo de dados, fluxo de autenticação e de
licenciamento: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) e
[docs/DATABASE.md](docs/DATABASE.md).

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic |
| Banco | MySQL 8+ (produção); SQLite apenas em testes automatizados |
| Autenticação | JWT (access + refresh), senha com Argon2id |
| Desktop | Python, PySide6 *(Fase 8)* |
| Cache/jobs | Redis *(reservado)* |
| Empacotamento | PyInstaller + Inno Setup *(Fases 8/10)* |

## Instalação (desenvolvimento)

Pré-requisitos: Python 3.12+, e **ou** Docker Desktop **ou** um MySQL 8
acessível.

```bash
git clone <repo> opsflow && cd opsflow
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # Windows
# .venv/bin/pip install -r requirements.txt       # Linux/macOS

cp .env.example .env
# edite .env: gere um JWT_SECRET
#   python -c "import secrets; print(secrets.token_urlsafe(64))"
# e aponte DATABASE_URL para o seu MySQL (ou deixe sqlite:///./opsflow_dev.db
# para rodar sem nenhum banco externo instalado)
```

## Desenvolvimento

```bash
# aplicar o schema
alembic -c database/migrations/alembic.ini upgrade head

# popular dados de demonstração (empresa, usuário admin, veículos, ...)
python database/seeds/seed_demo.py

# subir a API com reload automático
cd backend && uvicorn app.main:app --reload
# docs interativas em http://127.0.0.1:8000/docs
```

## Docker

```bash
cp .env.example docker/.env   # preencha JWT_SECRET, MYSQL_* se quiser customizar
docker compose -f docker/docker-compose.yml up -d
```

Sobe `api` (porta 8000) + `mysql` (3306) + `redis` (6379). Depois, de dentro
do container ou apontando `DATABASE_URL` para `localhost:3306`, rode as
migrations normalmente.

## Testes

```bash
pytest                 # roda tests/backend com cobertura (ver pyproject.toml)
```

A suíte atual cobre: bootstrap da aplicação, health check, hashing de senha
e uma guarda estrutural que garante que **toda** tabela de negócio possui
`tenant_id` (pré-condição do isolamento multi-tenant exigido nas seções
52/53 da especificação — os testes de ponta a ponta com dados reais de duas
empresas chegam na Fase 9).

## Build

Scripts de build (`build_desktop.bat`, `build_backend.bat`,
`build_installer.bat`) chegam nas Fases 8/10, junto do código desktop e do
instalador — não há nada para empacotar antes disso.

## Licenciamento

Cada empresa (`tenant`) tem uma `license` com `status`
(`ACTIVE`/`TRIAL`/`SUSPENDED`/`EXPIRED`/`CANCELLED`), validada pela API a
cada login — nunca por uma flag local no desktop. Detalhes:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#fluxo-de-licenciamento-seção-6).

## Segurança

HTTPS, JWT com refresh rotativo, hash Argon2id, bloqueio após tentativas
excessivas de login, isolamento por tenant, auditoria, segredos somente via
variável de ambiente (nunca no código-fonte). Detalhes e o que ainda está
pendente (hardening): Fase 11, documentado futuramente em `docs/SECURITY.md`.

## Roadmap

| Fase | Conteúdo | Status |
|---|---|---|
| 1 | Estrutura, banco, migrations, backend skeleton, config, Docker | ✅ Concluída |
| 2 | Autenticação e multi-tenancy | ✅ Concluída |
| 3 | Cadastros (veículos, motoristas, transportadoras, rotas) | ✅ Concluída |
| 4 | Operações (programação, timeline, status) | ✅ Concluída |
| 5 | Dashboard | Planejada |
| 6 | Relatórios/exportação | Planejada |
| 7 | Licenciamento (endpoints + enforcement) | Parcial (enforcement de limite de veículos já ativo) |
| 8 | Desktop (PySide6) | 🔶 Em andamento (login, shell, cadastros e operações adiantados; faltam dashboard/relatórios) |
| 9 | Testes (cobertura ampla, isolamento multi-tenant) | Planejada |
| 10 | Build e instalador | Planejada |
| 11 | Hardening de segurança | Planejada |
| 12 | Documentação final | Planejada |

Visão de mais longo prazo (mapas/GPS, integrações, IA, mobile):
[ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Licença

Software proprietário — todos os direitos reservados.
