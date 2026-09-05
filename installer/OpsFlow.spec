# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the OpsFlow desktop client (Fase 10).

Build from the repo root (works from anywhere, unlike a hand-tweaked
relative-path spec, because every path below is computed from `SPECPATH` —
the directory this file lives in, which PyInstaller injects automatically):

    pyinstaller installer/OpsFlow.spec

Output: `dist/OpsFlow/OpsFlow.exe` (+ its `_internal/` folder — this is a
one-folder build, not --onefile, because a single-exe build re-extracts
every PySide6 DLL into a temp dir on *every launch*, which is a slow and
unnecessary startup tax for an app people open daily). The Inno Setup
script (`installer/opsflow.iss`) packages that whole folder into a real
installer.

`desktop/tools/deployment_config.py` (the DATABASE_URL/JWT_SECRET .env
editor) is deliberately NOT bundled here. It edits the *backend's* `.env`
— but the backend isn't part of this installer at all (it runs on
whatever server hosts the API, never on a customer's desktop). Bundling it
was tried once: `Path(__file__)`-based climbing back to a "repo root" that
doesn't exist in a frozen EXE silently resolved to the wrong file — caught
by actually running the compiled EXE (not just the dev-mode script), which
showed placeholder defaults instead of the real config. That tool is for
whoever operates the backend, run directly from the source checkout
(`Configurar Implantacao.bat` at the repo root) where `__file__`-based
paths are correct — never something an end customer's desktop install
should carry.
"""
import os

REPO_ROOT = os.path.dirname(os.path.abspath(SPECPATH))  # noqa: F821 - SPECPATH is injected by PyInstaller
DESKTOP_DIR = os.path.join(REPO_ROOT, "desktop")
ICON_PATH = os.path.join(REPO_ROOT, "installer", "assets", "opsflow.ico")

a = Analysis(  # noqa: F821 - Analysis/PYZ/EXE/COLLECT are injected by PyInstaller
    [os.path.join(DESKTOP_DIR, "main.py")],
    pathex=[DESKTOP_DIR],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OpsFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH,
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="OpsFlow",
)
