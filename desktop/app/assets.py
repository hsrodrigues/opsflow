"""Resolve bundled asset paths (ícones, ...).

Funciona tanto rodando a partir do código-fonte (`python desktop/main.py`)
quanto de dentro do `.exe` empacotado pelo PyInstaller — nesse segundo caso
os arquivos listados em `datas=` (`installer/OpsFlow.spec`) são extraídos
soltos em `sys._MEIPASS`, não ao lado do código-fonte original. Um helper
único aqui evita essa checagem duplicada (e divergente) em cada arquivo que
precisa carregar um ícone.
"""
import sys
from pathlib import Path

_DESKTOP_DIR = Path(__file__).resolve().parents[1]  # desktop/


def asset_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", _DESKTOP_DIR))
    return base.joinpath(*parts)


def icon_path() -> Path:
    return asset_path("assets", "opsflow.ico")
