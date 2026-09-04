"""A tiny reusable QThread wrapper for calling the API without blocking the UI.

Every screen that calls `ApiClient` should go through this instead of
calling it directly on the UI thread — a slow/unreachable server must never
freeze the window (seção 31/44: loading indicators, never a frozen UI).
"""
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal


class ApiWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - deliberately broad: nothing may escape to Qt's event loop
            self.failed.emit(exc)
            return
        self.succeeded.emit(result)
