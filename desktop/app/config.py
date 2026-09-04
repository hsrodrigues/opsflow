"""Desktop client configuration.

Reads `OPSFLOW_API_URL` from the environment (falls back to the local dev
default) — the same "never hardcode where the server is" principle as the
backend's own `.env`-driven config, just simpler since the desktop has far
fewer settings.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DesktopConfig:
    api_base_url: str
    request_timeout_seconds: float
    app_version: str


def load_config() -> DesktopConfig:
    return DesktopConfig(
        api_base_url=os.environ.get("OPSFLOW_API_URL", "http://127.0.0.1:8000").rstrip("/"),
        request_timeout_seconds=float(os.environ.get("OPSFLOW_API_TIMEOUT", "10")),
        app_version="1.0.0",
    )
