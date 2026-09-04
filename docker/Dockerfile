# Imagem de produção/desenvolvimento do backend OpsFlow (FastAPI).
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências de sistema para compilar/rodar pymysql+cryptography e argon2-cffi.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY database/ database/

WORKDIR /app/backend

# LOG_DIR (settings.log_dir) é relativo ao WORKDIR acima; configure_logging()
# cria o diretório no startup — só precisamos garantir que o usuário não-root
# tenha permissão de escrita em /app.
RUN useradd --create-home --uid 1000 opsflow && chown -R opsflow:opsflow /app
USER opsflow

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
