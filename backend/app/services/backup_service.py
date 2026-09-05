"""Backup/restore do banco (seção 41 "Automações" + pedido explícito do
usuário: "crie uma rotina de backup, mas crie o backup e teste o backup e a
opção de restaurar também"). Usa `mysqldump`/`mysql` — os mesmos binários que
já vêm com qualquer instalação do MySQL Server — em vez de reimplementar um
dump via SQLAlchemy: é a ferramenta que o próprio MySQL garante que produz um
backup fiel (schema + dados + índices + foreign keys + triggers), e
restaurar é literalmente reexecutar o `.sql` gerado.

Operação de infraestrutura, cross-tenant por natureza (um `mysqldump` do
banco inteiro não tem como ser recortado por `tenant_id`) — por isso só é
exposta via `/api/v1/platform/backups`, atrás de `require_platform_admin`
(seção 54), nunca num endpoint de tenant comum.
"""
import glob
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError

logger = logging.getLogger("opsflow.backup")

_FILENAME_RE = re.compile(r"^opsflow_backup_\d{8}_\d{6}\.sql$")
_SUBPROCESS_TIMEOUT_SECONDS = 600


@dataclass
class _DbCredentials:
    host: str
    port: int
    user: str
    password: str
    database: str


def _parse_database_url(database_url: str) -> _DbCredentials:
    # "mysql+pymysql://user:pass@host:port/db" -> urlparse não entende o
    # driver depois do "+", então normalizamos o esquema antes de parsear.
    scheme, rest = database_url.split("://", 1)
    normalized = f"{scheme.split('+', 1)[0]}://{rest}"
    parsed = urlparse(normalized)
    return _DbCredentials(
        host=parsed.hostname or "127.0.0.1", port=parsed.port or 3306,
        user=parsed.username or "root", password=parsed.password or "",
        database=parsed.path.lstrip("/"),
    )


def _resolve_binary(name: str) -> str:
    """`mysqldump`/`mysql`, nesta ordem: PATH (já funciona out-of-the-box em
    Docker/Linux) -> `MYSQL_BIN_DIR` configurado -> instalação padrão do
    MySQL Installer no Windows (o instalador não adiciona ao PATH do
    sistema, então em dev isso quase sempre cai aqui)."""
    import shutil

    on_path = shutil.which(name)
    if on_path:
        return on_path

    settings = get_settings()
    candidates: list[str] = []
    if settings.mysql_bin_dir:
        candidates.append(str(Path(settings.mysql_bin_dir) / f"{name}.exe"))
    candidates.extend(sorted(glob.glob(rf"C:\Program Files\MySQL\MySQL Server *\bin\{name}.exe"), reverse=True))
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate

    raise ValidationFailedError(
        f"Não encontrei o executável '{name}'. Configure MYSQL_BIN_DIR no .env apontando "
        "para a pasta bin/ da instalação do MySQL Server."
    )


def _subprocess_env(password: str) -> dict:
    # A senha vai por variável de ambiente (MYSQL_PWD), nunca por
    # `--password=...` na linha de comando — evita ficar visível pra
    # qualquer outro processo que liste os argumentos deste (`tasklist`,
    # `/proc/<pid>/cmdline`, etc.) e também evita o aviso do próprio
    # mysqldump/mysql sobre senha na linha de comando ser insegura.
    return {**os.environ, "MYSQL_PWD": password}


def backup_dir() -> Path:
    path = Path(get_settings().backup_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_backup() -> Path:
    """Roda `mysqldump` contra o banco configurado e grava um `.sql` com
    timestamp. Levanta `ValidationFailedError` se o `mysqldump` falhar ou o
    arquivo sair vazio — uma falha silenciosa aqui destruiria a rotina
    inteira sem ninguém perceber até o dia de precisar restaurar."""
    settings = get_settings()
    creds = _parse_database_url(settings.database_url)
    mysqldump = _resolve_binary("mysqldump")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    target = backup_dir() / f"opsflow_backup_{timestamp}.sql"

    command = [
        mysqldump, f"--host={creds.host}", f"--port={creds.port}", f"--user={creds.user}",
        "--single-transaction", "--routines", "--triggers", "--events",
        # Sem isso, um servidor com GTID habilitado (padrão em instalações
        # recentes do MySQL) grava um `SET @@GLOBAL.GTID_PURGED=...` no dump
        # — e restaurar esse dump de volta no MESMO servidor falha com
        # "GTID_PURGED cannot be changed: ... must not overlap with
        # GTID_EXECUTED", porque o servidor já executou transações depois
        # daquele ponto. `--set-gtid-purged=OFF` é a recomendação oficial do
        # MySQL para dump/restore dentro do mesmo servidor (não é uma cópia
        # pra um replica novo, onde esse controle faria sentido manter).
        "--set-gtid-purged=OFF",
        creds.database,
    ]
    result = subprocess.run(
        command, capture_output=True, env=_subprocess_env(creds.password), timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        logger.error("mysqldump falhou (código %s): %s", result.returncode, stderr)
        raise ValidationFailedError(f"Falha ao gerar backup: {stderr.strip() or 'erro desconhecido do mysqldump.'}")

    target.write_bytes(result.stdout)
    if target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise ValidationFailedError("mysqldump gerou um arquivo vazio — backup abortado.")

    logger.info("Backup criado: %s (%d bytes)", target.name, target.stat().st_size)
    _prune_old_backups(settings.backup_retention_count)
    return target


def _prune_old_backups(keep: int) -> None:
    for stale in list_backups()[keep:]:
        stale.unlink(missing_ok=True)
        logger.info("Backup antigo removido (retenção = %d): %s", keep, stale.name)


def parse_backup_timestamp(filename: str) -> datetime:
    """`"opsflow_backup_20260905_143000.sql"` -> the UTC moment it was taken
    (embedded in the name itself, per `create_backup` — more reliable than
    the file's `mtime`, which a copy/restore-of-the-backups-folder could
    change without the backup itself being any older or newer)."""
    raw = filename.removeprefix("opsflow_backup_").removesuffix(".sql")
    return datetime.strptime(raw, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)


def list_backups() -> list[Path]:
    """Mais recente primeiro — o nome do arquivo (timestamp `%Y%m%d_%H%M%S`)
    já ordena cronologicamente como string, sem precisar olhar `mtime`."""
    return sorted(
        (p for p in backup_dir().glob("opsflow_backup_*.sql") if _FILENAME_RE.match(p.name)),
        key=lambda p: p.name, reverse=True,
    )


def restore_backup(filename: str) -> None:
    """Restaura um `.sql` gerado por `create_backup` — SOBRESCREVE o banco
    atual (é literalmente reexecutar o dump, `DROP`/`CREATE TABLE`/`INSERT`
    incluídos). Só aceita nomes que batem com o padrão de `create_backup`
    (nunca um caminho arbitrário vindo da API): sem essa validação, um
    `filename` como `../../etc/algo` viraria leitura arbitrária de arquivo
    do disco alimentada direto pro `mysql` client."""
    if not _FILENAME_RE.match(filename):
        raise ValidationFailedError("Nome de arquivo de backup inválido.")

    path = backup_dir() / filename
    if not path.is_file():
        raise ValidationFailedError("Arquivo de backup não encontrado.")

    settings = get_settings()
    creds = _parse_database_url(settings.database_url)
    mysql_client = _resolve_binary("mysql")

    command = [mysql_client, f"--host={creds.host}", f"--port={creds.port}", f"--user={creds.user}", creds.database]
    with path.open("rb") as sql_file:
        result = subprocess.run(
            command, stdin=sql_file, capture_output=True, env=_subprocess_env(creds.password),
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        logger.error("Restore falhou (código %s): %s", result.returncode, stderr)
        raise ValidationFailedError(f"Falha ao restaurar backup: {stderr.strip() or 'erro desconhecido do mysql.'}")

    logger.info("Backup restaurado: %s", filename)
