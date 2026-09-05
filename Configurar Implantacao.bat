@echo off
REM Abre a tela de configuração de implantação (DATABASE_URL/JWT_SECRET)
REM sem precisar digitar nenhum comando — só dar dois cliques neste arquivo.
REM Roda a partir do checkout do projeto (não é pra ser instalado no
REM cliente final — veja o comentário no topo de installer\OpsFlow.spec).
cd /d "%~dp0"
".venv\Scripts\python.exe" "desktop\tools\deployment_config.py"
