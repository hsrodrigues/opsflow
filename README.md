<div align="center">

# OpsFlow

**Gestão Operacional Inteligente**

Plataforma SaaS/desktop multi-tenant de gestão operacional e logística — para
empresas que hoje controlam sua operação em planilhas, WhatsApp e controles
manuais.

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-blue)
![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white)
![PySide6](https://img.shields.io/badge/desktop-PySide6%20(Qt)-41CD52?logo=qt&logoColor=white)
![MySQL](https://img.shields.io/badge/banco-MySQL%208-4479A1?logo=mysql&logoColor=white)
![License](https://img.shields.io/badge/licença-proprietária-red)

</div>

> **Status do projeto:** em desenvolvimento por fases, construído sobre uma
> especificação funcional completa. Este README reflete exatamente o que
> está implementado e testado agora — nada aqui é aspiracional. Ver
> [Roadmap](#roadmap) para o que falta.

## Sumário

- [Capturas de tela](#-capturas-de-tela)
- [Funcionalidades](#-funcionalidades)
- [Arquitetura](#-arquitetura)
- [Stack](#-stack)
- [Instalação](#-instalação-desenvolvimento)
- [Desenvolvimento](#-desenvolvimento)
- [Docker](#-docker)
- [Testes](#-testes)
- [Segurança](#-segurança)
- [Roadmap](#roadmap)

## 📸 Capturas de tela

<table>
<tr>
<td width="50%"><img src="docs/screenshots/login.png" alt="Tela de login"></td>
<td width="50%"><img src="docs/screenshots/dashboard.png" alt="Dashboard"></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/veiculos.png" alt="Cadastro de veículos"></td>
<td width="50%"><img src="docs/screenshots/centro-operacoes.png" alt="Centro de Operações"></td>
</tr>
</table>

<details>
<summary>Tema escuro</summary>
<img src="docs/screenshots/tema-escuro.png" alt="Dashboard em tema escuro">
</details>

## ✅ Funcionalidades

Implementado, testado e rodando contra MySQL real — não protótipo visual:

| Módulo | O que tem |
|---|---|
| **Arquitetura & multi-tenant** | Schema completo (34 tabelas), isolamento por `tenant_id` centralizado em `TenantRepository`, RBAC com 5 papéis e matriz de permissões, catálogo de planos, migrations Alembic |
| **Autenticação** | Login/refresh/logout com JWT + refresh token rotativo, bloqueio por tentativas excessivas, RBAC ponta a ponta |
| **Cadastros** | Veículos, Motoristas, Transportadoras, Rotas e Produtos (com unidade de medida própria) — CRUD completo: busca, filtros, paginação, validação de duplicidade, soft delete, auditoria, máscara de CPF/CNPJ/telefone |
| **Operações** | Programação operacional com timeline de status automática (`schedule → operation → status_history`), Centro de Operações ao vivo (contadores + quadro de operações, seção 21 da spec) |
| **Ocorrências** | CRUD completo (seção 14) — tipo configurável, severidade, status, vínculo com veículo/motorista; registrar um "Acidente" bloqueia o veículo automaticamente |
| **Dashboard** | 9 KPIs (operações hoje, concluídas, atrasadas, tempo médio, taxa de conclusão, ...) + 3 gráficos (QtCharts) com filtro de período — seções 15/16 |
| **Relatórios** | Operações, Ocorrências, Veículos e Ranking de transportadoras — prévia na tela e exportação em Excel/CSV/PDF com cabeçalho, período e indicadores (seção 17) |
| **Gestão de usuários** | ADMIN_EMPRESA convida a equipe, define papel, ativa/desativa e redefine senha — nunca exclui de verdade (preserva a auditoria) |
| **Notificações & automações** | 4 robôs em background (APScheduler): detecção automática de atraso, alerta de CNH vencendo, expiração automática de licença, backup diário do banco; sino de notificações no desktop mostra tudo isso em tempo real |
| **Licenciamento** | Licença por tenant (`ACTIVE`/`TRIAL`/`SUSPENDED`/`EXPIRED`/`CANCELLED`), validada pela API a cada login, enforcement do limite de veículos/usuários do plano, tela própria com uso real vs. limite. Autoatendimento: `SUPER_ADMIN` gera uma chave solta (sem empresa vinculada ainda); o cliente a resgata sozinho na tela de login, criando a própria empresa e o próprio usuário admin, e já sai logado |
| **Console de plataforma** | Exclusivo de `SUPER_ADMIN` (usuário de plataforma, sem empresa): empresas clientes (criar, trocar plano, suspender/reativar), chaves de ativação (gerar, acompanhar quais já foram resgatadas), backups (gerar sob demanda, listar, restaurar) — janela própria, sem sidebar de cadastros |
| **Configurações** | Autoatendimento: qualquer usuário edita o próprio nome/telefone (`PATCH /auth/me`) sem depender de permissão de admin; sem "esqueci minha senha" de propósito — trocar senha é sempre uma ação do admin da empresa, na tela Usuários |
| **Backup/restore** | `mysqldump`/`mysql` de verdade (schema + dados + triggers), robô diário automático com retenção configurável, geração sob demanda e restauração pelo Console de Plataforma |
| **Stored procedures** | 3 procedures MySQL pra reduzir processo manual: duplicar toda a programação de um dia pra outra data (um clique), fechar automaticamente operações penduradas há mais de N horas num status intermediário (robô), arquivar operações/ocorrências antigas já concluídas pra tabelas de arquivo (sob demanda, pelo Console de Plataforma) — com fallback em Python/ORM pra qualquer banco que não seja MySQL |
| **Desktop (PySide6)** | Login, shell navegável (sidebar por seção, tema claro/escuro, indicador de conexão), todas as telas acima já com visual final |

Planejado, fase a fase — ver [ARCHITECTURE.md](docs/ARCHITECTURE.md) e a
seção [Roadmap](#roadmap).

## 🏗️ Arquitetura

```
        Desktop (PySide6)  --HTTPS/JWT-->  API (FastAPI)  -->  MySQL 8 (SQLAlchemy 2.x)
                                                  │
                                                  ├─→ Redis (cache/jobs, reservado)
                                                  └─→ APScheduler (robôs em background)
```

Detalhes completos, modelo de dados, fluxo de autenticação e de
licenciamento: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) e
[docs/DATABASE.md](docs/DATABASE.md).

## 🧱 Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic |
| Banco | MySQL 8+ (produção e dev); SQLite isolado nos testes automatizados |
| Autenticação | JWT (access + refresh), senha com Argon2id |
| Jobs | APScheduler (detecção de atraso, alertas de CNH, expiração de licença) |
| Relatórios | openpyxl (Excel), reportlab (PDF) |
| Desktop | Python, PySide6 (Qt) |
| Cache | Redis *(reservado para quando o volume justificar)* |
| Empacotamento | PyInstaller + Inno Setup *(Fase 10)* |

## 🚀 Instalação (desenvolvimento)

Pré-requisitos: Python 3.12+, e **ou** Docker Desktop **ou** um MySQL 8
acessível (Community Server, XAMPP, etc.).

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

Prefere não editar o `.env` na mão? Dê dois cliques em `Configurar Implantacao.bat`
(raiz do projeto) — abre uma tela pra preencher host/porta/usuário/senha/banco,
testar a conexão de verdade antes de salvar, e gerar um novo `JWT_SECRET` com um
clique. Reinicie o backend depois de salvar (ele só lê o `.env` na inicialização).

## 🛠️ Desenvolvimento

```bash
# aplicar o schema
alembic -c database/migrations/alembic.ini upgrade head

# popular dados de demonstração (empresa, usuário admin, veículos, ...)
python database/seeds/seed_demo.py

# subir a API com reload automático (a partir da raiz do projeto)
uvicorn app.main:app --app-dir backend --reload
# docs interativas em http://127.0.0.1:8000/docs

# abrir o desktop (com a API acima já rodando)
python desktop/main.py
```

### Sincronização automática com o GitHub (Windows)

Para iniciar o sincronizador no login do Windows, dê dois cliques em
`Configurar Sync Automatico.bat`. Ele observa alterações no projeto, aguarda
30 segundos sem novas alterações, cria um commit e envia para `origin/master`.
Conflitos de rebase não são forçados; ficam registrados em
`logs/auto-sync.log` para resolução manual.

## 🐳 Docker

```bash
cp .env.example docker/.env   # preencha JWT_SECRET, MYSQL_* se quiser customizar
docker compose -f docker/docker-compose.yml up -d
```

Sobe `api` (porta 8000) + `mysql` (3306) + `redis` (6379). Depois, de dentro
do container ou apontando `DATABASE_URL` para `localhost:3306`, rode as
migrations normalmente.

## 🧪 Testes

```bash
pytest                 # roda tests/backend com cobertura (ver pyproject.toml)
```

139 testes automatizados (93% de cobertura de linha), sempre contra um
SQLite isolado (nunca o banco de desenvolvimento) — cobrindo autenticação
(incluindo o autoatendimento de perfil, `PATCH /auth/me`, liberado pra
qualquer papel), isolamento multi-tenant com dados reais de duas empresas
(seções 52/53 da spec), CRUD de todos os cadastros, o fluxo de
programação/status/timeline (incluindo exclusão restrita a itens ainda não
iniciados), gestão de usuários (papel atribuível, limite de plano,
autodesativação bloqueada), geração dos 4 relatórios nos 3 formatos de
exportação, o bloqueio automático de veículo ao registrar um acidente, o
console de plataforma (onboarding de empresa, troca de plano, suspensão —
sempre confirmando que nenhum papel de empresa cliente chega perto disso),
o fluxo de ativação por chave solta (gerar → resgatar sem autenticação →
login automático → reuso bloqueado) e os endpoints de backup/restore
(permissão restrita a `SUPER_ADMIN`; a chamada real a `mysqldump`/`mysql`
é mockada aqui — verificada à parte, contra um MySQL de verdade). Os 4
robôs em background são testados chamando `run()` diretamente, nunca via
APScheduler de verdade (evitaria uma suíte instável).

## 🔐 Segurança

JWT com refresh rotativo, hash Argon2id, bloqueio após tentativas excessivas
de login, isolamento por tenant, auditoria, segredos somente via variável de
ambiente (nunca no código-fonte), rate limiting, cabeçalhos de segurança,
`/docs` desligado fora de desenvolvimento. HTTPS é responsabilidade do
proxy/load balancer na frente da API, não do código em si. Detalhes
completos, item a item, com o arquivo/teste que garante cada um:
[docs/SECURITY.md](docs/SECURITY.md).

<a id="roadmap"></a>
## 🗺️ Roadmap

| Fase | Conteúdo | Status |
|---|---|---|
| 1 | Estrutura, banco, migrations, backend skeleton, config, Docker | ✅ Concluída |
| 2 | Autenticação e multi-tenancy | ✅ Concluída |
| 3 | Cadastros (veículos, motoristas, transportadoras, rotas) | ✅ Concluída |
| 4 | Operações (programação, timeline, status) | ✅ Concluída |
| — | Notificações + automações em background *(adiantado da seção 41)* | ✅ Concluída |
| 5 | Dashboard | ✅ Concluída (inclui Ocorrências, seção 14, como pré-requisito) |
| 6 | Relatórios/exportação | ✅ Concluída — 4 tipos, 3 formatos, prévia + exportação, backend e desktop |
| 7 | Licenciamento (endpoints + enforcement) | ✅ Concluída — enforcement de limite de veículos/usuários, tela de uso real vs. limite |
| — | Gestão de usuários (convidar/editar/desativar equipe) *(fora do escopo original, adiantado por valor claro)* | ✅ Concluída |
| — | Console de plataforma para `SUPER_ADMIN` (seção 54): criar empresas, trocar plano, suspender/reativar licença *(fora do escopo original)* | ✅ Concluída |
| — | Ativação por chave solta (`SUPER_ADMIN` gera, cliente resgata sozinho) e Configurações/Meu Perfil *(fora do escopo original)* | ✅ Concluída |
| — | Backup/restore do banco (robô diário + sob demanda, pelo Console de Plataforma) *(adiantado da seção 41)* | ✅ Concluída |
| 8 | Desktop (PySide6) | ✅ Concluída — login, shell, todos os cadastros, operações, dashboard, relatórios, usuários, configurações, licença e console de plataforma |
| — | Stored procedures (duplicar programação, fechar pendências, arquivar dados antigos) *(fora do escopo original, pedido explícito)* | ✅ Concluída |
| 9 | Testes (cobertura ampla, isolamento multi-tenant) | ✅ Concluída — 139 testes, 93% de cobertura de linha |
| 10 | Build e instalador | ✅ Concluída — PyInstaller (one-folder) + instalador Inno Setup, testado com instalação/execução/desinstalação silenciosa reais |
| 11 | Hardening de segurança | ✅ Concluída — rate limiting de verdade, docs desligados fora de dev, cabeçalhos de segurança, CORS sem a combinação inválida wildcard+credentials, `/api/health` sem vazar credencial — ver [SECURITY.md](docs/SECURITY.md) |
| 12 | Documentação final | 🔶 Em andamento |

Visão de mais longo prazo (mapas/GPS, integrações, IA, mobile):
[ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

<div align="center">

**Licença:** software proprietário — todos os direitos reservados.

</div>
