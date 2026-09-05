<div align="center">

# OpsFlow

### Gestão operacional e logística em um só lugar

Plataforma SaaS/desktop multi-tenant para empresas que querem substituir
planilhas, WhatsApp e controles manuais por uma operação organizada,
auditável e segura.

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-blue)
![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white)
![PySide6](https://img.shields.io/badge/desktop-PySide6%20(Qt)-41CD52?logo=qt&logoColor=white)
![MySQL](https://img.shields.io/badge/banco-MySQL%208-4479A1?logo=mysql&logoColor=white)
![Licença](https://img.shields.io/badge/licença-proprietária-red)

[Funcionalidades](#funcionalidades) ·
[Instalação](#instalação) ·
[Documentação](#documentação) ·
[Roadmap](#roadmap)

</div>

> **Estado atual:** o projeto está em desenvolvimento por fases. Esta página
> descreve somente o que já está implementado e testado.

## Sobre o projeto

O OpsFlow conecta o desktop usado pela equipe à API e ao banco de dados,
oferecendo:

- **Operação:** cadastros, programação, timeline de status e centro de
  operações.
- **Gestão:** dashboard, ocorrências, relatórios, usuários e configurações.
- **Plataforma:** licenciamento por empresa, ativação por chave e console
  exclusivo para `SUPER_ADMIN`.
- **Confiabilidade:** auditoria, isolamento multi-tenant, backups, automações
  em background e hardening de segurança.

## Funcionalidades

### Operação diária

| Módulo | Entregas |
| --- | --- |
| Cadastros | Veículos, motoristas, transportadoras, rotas e produtos com CRUD, busca, filtros, paginação, validação, soft delete e auditoria. |
| Programação | Criação de programações, operações derivadas, timeline de status e duplicação de programação por data. |
| Centro de operações | Contadores e quadro operacional ao vivo para acompanhar a execução. |
| Ocorrências | Tipos configuráveis, severidade, status e vínculo com veículo ou motorista; acidentes bloqueiam veículos e ocorrências críticas bloqueiam motoristas automaticamente. |

### Gestão e análise

| Módulo | Entregas |
| --- | --- |
| Dashboard | KPIs operacionais, gráficos e filtros por período. |
| Relatórios | Operações, ocorrências, veículos e ranking de transportadoras; prévia e exportação em Excel, CSV e PDF. |
| Usuários | Convite, papéis, ativação/desativação e redefinição de senha pelo administrador da empresa. |
| Notificações | Sino no desktop com alertas de atraso, CNH, licença e eventos operacionais. |

### Plataforma e infraestrutura

| Módulo | Entregas |
| --- | --- |
| Multi-tenant e RBAC | Isolamento por empresa e cinco papéis: `SUPER_ADMIN`, `ADMIN_EMPRESA`, `SUPERVISOR`, `OPERADOR` e `VISUALIZADOR`. |
| Licenciamento | Planos, limites de usuários/veículos, estados de licença, tela de uso e ativação por chave sem vínculo prévio. |
| Console de plataforma | Gestão de empresas, planos, licenças, chaves de ativação e backups. |
| Automações | Detecção de atrasos, alertas de CNH, expiração de licença, backup diário, fechamento de operações pendentes e arquivamento. |
| Segurança | JWT com refresh rotativo, Argon2id, rate limiting, headers de segurança, auditoria, CORS configurável e documentação da API desligada fora de desenvolvimento. |

## Capturas de tela

<table>
<tr>
<td width="50%"><img src="docs/screenshots/login.png" alt="Tela de login"></td>
<td width="50%"><img src="docs/screenshots/dashboard.png" alt="Dashboard"></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/veiculos.png" alt="Cadastro de veículos"></td>
<td width="50%"><img src="docs/screenshots/centro-operacoes.png" alt="Centro de operações"></td>
</tr>
</table>

<details>
<summary>Ver tema escuro</summary>
<img src="docs/screenshots/tema-escuro.png" alt="Dashboard em tema escuro">
</details>

## Arquitetura

```text
Desktop (PySide6) -- HTTPS/JWT --> API (FastAPI) --> MySQL 8
                                      |                 |
                                      +-- APScheduler   +-- SQLAlchemy 2.x
                                      +-- Redis (reservado)
```

| Camada | Tecnologia |
| --- | --- |
| Desktop | Python + PySide6 |
| Backend | Python 3.12+ + FastAPI |
| Persistência | SQLAlchemy 2.x + MySQL 8+ |
| Validação | Pydantic v2 |
| Autenticação | JWT + Argon2id |
| Jobs | APScheduler |
| Relatórios | openpyxl + reportlab |
| Empacotamento | PyInstaller + Inno Setup |

Veja os detalhes de camadas, modelo de dados, autenticação e licenciamento em
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) e
[docs/DATABASE.md](docs/DATABASE.md).

## Instalação

### Pré-requisitos

- Python 3.12+
- Docker Desktop **ou** MySQL 8 acessível
- Git

### Configuração local

```bash
git clone https://github.com/hsrodrigues/opsflow.git
cd opsflow

python -m venv .venv
# Windows
.\.venv\Scripts\pip install -r requirements.txt
# Linux/macOS
# .venv/bin/pip install -r requirements.txt

copy .env.example .env
```

Edite o `.env` e defina ao menos `DATABASE_URL` e `JWT_SECRET`. Para gerar um
segredo:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

No Windows, `Configurar Implantacao.bat` abre uma tela para preencher e testar
a conexão do banco e gerar o `JWT_SECRET`.

## Executando

### Backend

```bash
alembic -c database/migrations/alembic.ini upgrade head
python database/seeds/seed_demo.py
uvicorn app.main:app --app-dir backend --reload
```

API local: <http://127.0.0.1:8000>
Documentação interativa: <http://127.0.0.1:8000/docs> (somente em
desenvolvimento)

### Desktop

Com a API em execução:

```bash
python desktop/main.py
```

### Docker

```bash
copy .env.example docker\.env
docker compose -f docker/docker-compose.yml up -d
```

O compose sobe API, MySQL e Redis.

### Sincronização automática no Windows

Para sincronizar alterações locais automaticamente com o GitHub, execute
`Configurar Sync Automatico.bat`. O monitor aguarda 30 segundos sem novas
alterações, cria um commit e envia para `origin/master`. Conflitos de rebase
não são forçados e ficam registrados em `logs/auto-sync.log`.

## Testes

```bash
pytest
```

A suíte usa SQLite isolado e cobre autenticação, multi-tenancy, CRUD,
licenciamento, relatórios, automações, backups, ocorrências e segurança.

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [Guia do usuário](docs/GUIA_DO_USUARIO.md) | Uso do sistema por papel e por tela. |
| [Arquitetura](docs/ARCHITECTURE.md) | Decisões técnicas e fluxos principais. |
| [Banco de dados](docs/DATABASE.md) | Modelo, migrations e procedimentos. |
| [Segurança](docs/SECURITY.md) | Controles implementados e orientações de implantação. |
| [Licença](LICENSE) | Termos de uso do software. |

## Roadmap

| Fase | Entrega | Status |
| --- | --- | --- |
| 1-4 | Base, autenticação, multi-tenancy, cadastros e operações | ✅ Concluídas |
| 5-7 | Dashboard, relatórios e licenciamento | ✅ Concluídas |
| 8 | Desktop PySide6 | ✅ Concluída |
| 9 | Testes e cobertura ampla | ✅ Concluída |
| 10 | Build e instalador | ✅ Concluída |
| 11 | Hardening de segurança | ✅ Concluída |
| 12 | Documentação final | ✅ Concluída |

Próximas possibilidades: mapas/GPS, integrações, inteligência artificial e
aplicativo mobile.

## Licença

Software proprietário — todos os direitos reservados. Consulte
[LICENSE](LICENSE).
