"""Thin HTTP client for the OpsFlow API.

Every method returns plain `dict`s (the API's own JSON) or raises
`ApiError`/`ConnectionUnavailableError` — never lets an `httpx` exception
escape to the UI layer, per seção 31 ("nunca permitir que uma exceção
derrube silenciosamente a aplicação").
"""
import logging

import httpx

from app.config import DesktopConfig
from services.errors import ApiError, ConnectionUnavailableError

logger = logging.getLogger("opsflow.desktop")


class ApiClient:
    def __init__(self, config: DesktopConfig) -> None:
        self._config = config
        self._client = httpx.Client(base_url=config.api_base_url, timeout=config.request_timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def check_health(self) -> dict:
        return self._request("GET", "/api/health")

    def login(self, email: str, password: str, remember: bool) -> dict:
        return self._request(
            "POST", "/api/v1/auth/login", json={"email": email, "password": password, "remember": remember}
        )

    def refresh(self, refresh_token: str) -> dict:
        return self._request("POST", "/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    def logout(self, refresh_token: str) -> None:
        self._request("POST", "/api/v1/auth/logout", json={"refresh_token": refresh_token})

    def get_me(self, access_token: str) -> dict:
        return self._request("GET", "/api/v1/auth/me", access_token=access_token)

    def update_my_profile(self, access_token: str, payload: dict) -> dict:
        return self._request("PATCH", "/api/v1/auth/me", json=payload, access_token=access_token)

    # --- CRUD genérico de cadastro (seção 9/10/11: mesmo padrão em todos) ---

    def _list(self, resource: str, access_token: str, **params) -> dict:
        return self._request("GET", f"/api/v1/{resource}", params=params, access_token=access_token)

    def _create(self, resource: str, access_token: str, payload: dict) -> dict:
        return self._request("POST", f"/api/v1/{resource}", json=payload, access_token=access_token)

    def _update(self, resource: str, access_token: str, record_id: int, payload: dict) -> dict:
        return self._request("PATCH", f"/api/v1/{resource}/{record_id}", json=payload, access_token=access_token)

    def _delete(self, resource: str, access_token: str, record_id: int) -> None:
        self._request("DELETE", f"/api/v1/{resource}/{record_id}", access_token=access_token)

    # --- Veículos (seção 9) ---

    def list_vehicles(self, access_token: str, **params) -> dict:
        return self._list("vehicles", access_token, **params)

    def create_vehicle(self, access_token: str, payload: dict) -> dict:
        return self._create("vehicles", access_token, payload)

    def update_vehicle(self, access_token: str, vehicle_id: int, payload: dict) -> dict:
        return self._update("vehicles", access_token, vehicle_id, payload)

    def delete_vehicle(self, access_token: str, vehicle_id: int) -> None:
        self._delete("vehicles", access_token, vehicle_id)

    # --- Motoristas (seção 10) ---

    def list_drivers(self, access_token: str, **params) -> dict:
        return self._list("drivers", access_token, **params)

    def create_driver(self, access_token: str, payload: dict) -> dict:
        return self._create("drivers", access_token, payload)

    def update_driver(self, access_token: str, driver_id: int, payload: dict) -> dict:
        return self._update("drivers", access_token, driver_id, payload)

    def delete_driver(self, access_token: str, driver_id: int) -> None:
        self._delete("drivers", access_token, driver_id)

    # --- Transportadoras (seção 11) ---

    def list_carriers(self, access_token: str, **params) -> dict:
        return self._list("carriers", access_token, **params)

    def create_carrier(self, access_token: str, payload: dict) -> dict:
        return self._create("carriers", access_token, payload)

    def update_carrier(self, access_token: str, carrier_id: int, payload: dict) -> dict:
        return self._update("carriers", access_token, carrier_id, payload)

    def delete_carrier(self, access_token: str, carrier_id: int) -> None:
        self._delete("carriers", access_token, carrier_id)

    # --- Rotas (seção 12) ---

    def list_routes(self, access_token: str, **params) -> dict:
        return self._list("routes", access_token, **params)

    def create_route(self, access_token: str, payload: dict) -> dict:
        return self._create("routes", access_token, payload)

    def update_route(self, access_token: str, route_id: int, payload: dict) -> dict:
        return self._update("routes", access_token, route_id, payload)

    def delete_route(self, access_token: str, route_id: int) -> None:
        self._delete("routes", access_token, route_id)

    # --- Console de plataforma (seção 54, exclusivo de SUPER_ADMIN) ---

    def list_tenants(self, access_token: str) -> list:
        return self._request("GET", "/api/v1/platform/tenants", access_token=access_token)

    def create_tenant(self, access_token: str, payload: dict) -> dict:
        return self._request("POST", "/api/v1/platform/tenants", json=payload, access_token=access_token)

    def update_tenant(self, access_token: str, tenant_id: int, payload: dict) -> dict:
        return self._request(
            "PATCH", f"/api/v1/platform/tenants/{tenant_id}", json=payload, access_token=access_token,
        )

    def update_tenant_license(self, access_token: str, tenant_id: int, payload: dict) -> dict:
        return self._request(
            "PATCH", f"/api/v1/platform/tenants/{tenant_id}/license", json=payload, access_token=access_token,
        )

    def regenerate_license_key(self, access_token: str, tenant_id: int) -> dict:
        return self._request(
            "POST", f"/api/v1/platform/tenants/{tenant_id}/license/regenerate-key", access_token=access_token,
        )

    def list_license_keys(self, access_token: str) -> list:
        return self._request("GET", "/api/v1/platform/license-keys", access_token=access_token)

    def generate_license_key(self, access_token: str, payload: dict) -> dict:
        return self._request("POST", "/api/v1/platform/license-keys", json=payload, access_token=access_token)

    # Backup/restore rodam `mysqldump`/`mysql` de verdade no servidor — pode
    # levar bem mais que o timeout padrão de requests comuns num banco maior
    # que o de desenvolvimento, então usam um teto próprio, generoso.
    _BACKUP_TIMEOUT_SECONDS = 120.0

    def list_backups(self, access_token: str) -> list:
        return self._request("GET", "/api/v1/platform/backups", access_token=access_token)

    def create_backup(self, access_token: str) -> dict:
        return self._request(
            "POST", "/api/v1/platform/backups", access_token=access_token, timeout=self._BACKUP_TIMEOUT_SECONDS,
        )

    def restore_backup(self, access_token: str, filename: str) -> None:
        self._request(
            "POST", "/api/v1/platform/backups/restore", json={"filename": filename}, access_token=access_token,
            timeout=self._BACKUP_TIMEOUT_SECONDS,
        )

    def archive_old_records(self, access_token: str, older_than_months: int) -> dict:
        return self._request(
            "POST", "/api/v1/platform/archive", json={"older_than_months": older_than_months},
            access_token=access_token, timeout=self._BACKUP_TIMEOUT_SECONDS,
        )

    # --- Ativação (sem login — cliente novo resgatando uma chave) ---

    def activate_license(self, payload: dict) -> dict:
        return self._request("POST", "/api/v1/activation/activate", json=payload)

    # --- Licença (seção 6/7) ---

    def get_license(self, access_token: str) -> dict:
        return self._request("GET", "/api/v1/license", access_token=access_token)

    # --- Usuários (gestão de equipe) ---

    def list_users(self, access_token: str, **params) -> dict:
        return self._list("users", access_token, **params)

    def create_user(self, access_token: str, payload: dict) -> dict:
        return self._create("users", access_token, payload)

    def update_user(self, access_token: str, user_id: int, payload: dict) -> dict:
        return self._update("users", access_token, user_id, payload)

    def reset_user_password(self, access_token: str, user_id: int, new_password: str) -> None:
        self._request(
            "POST", f"/api/v1/users/{user_id}/reset-password", json={"new_password": new_password},
            access_token=access_token,
        )

    # --- Produtos ---

    def list_products(self, access_token: str, **params) -> dict:
        return self._list("products", access_token, **params)

    def create_product(self, access_token: str, payload: dict) -> dict:
        return self._create("products", access_token, payload)

    def update_product(self, access_token: str, product_id: int, payload: dict) -> dict:
        return self._update("products", access_token, product_id, payload)

    def delete_product(self, access_token: str, product_id: int) -> None:
        self._delete("products", access_token, product_id)

    # --- Programação (seção 13) ---

    def list_schedule_items(self, access_token: str, **params) -> dict:
        return self._list("schedules/items", access_token, **params)

    def create_schedule_item(self, access_token: str, payload: dict) -> dict:
        return self._create("schedules/items", access_token, payload)

    def update_schedule_item(self, access_token: str, item_id: int, payload: dict) -> dict:
        return self._update("schedules/items", access_token, item_id, payload)

    def delete_schedule_item(self, access_token: str, item_id: int) -> None:
        self._delete("schedules/items", access_token, item_id)

    def change_schedule_item_status(self, access_token: str, item_id: int, status: str, notes: str | None) -> dict:
        return self._request(
            "POST", f"/api/v1/schedules/items/{item_id}/status", json={"status": status, "notes": notes},
            access_token=access_token,
        )

    def get_schedule_item_history(self, access_token: str, item_id: int) -> list:
        return self._request(
            "GET", f"/api/v1/schedules/items/{item_id}/history", access_token=access_token,
        )

    def duplicate_schedule(self, access_token: str, source_date: str, target_date: str) -> dict:
        return self._request(
            "POST", "/api/v1/schedules/duplicate",
            json={"source_date": source_date, "target_date": target_date}, access_token=access_token,
        )

    # --- Centro de Operações (seção 21) ---

    def list_operations(self, access_token: str) -> list:
        return self._request("GET", "/api/v1/operations", access_token=access_token)

    def get_operations_summary(self, access_token: str, **params) -> dict:
        return self._request("GET", "/api/v1/operations/summary", params=params, access_token=access_token)

    # --- Dashboard (seção 15/16) ---

    def get_dashboard_summary(self, access_token: str, **params) -> dict:
        return self._request("GET", "/api/v1/dashboard/summary", params=params, access_token=access_token)

    def get_dashboard_charts(self, access_token: str, **params) -> dict:
        return self._request("GET", "/api/v1/dashboard/charts", params=params, access_token=access_token)

    # --- Ocorrências (seção 14) ---

    def list_occurrences(self, access_token: str, **params) -> dict:
        return self._list("occurrences", access_token, **params)

    def create_occurrence(self, access_token: str, payload: dict) -> dict:
        return self._create("occurrences", access_token, payload)

    def update_occurrence(self, access_token: str, occurrence_id: int, payload: dict) -> dict:
        return self._update("occurrences", access_token, occurrence_id, payload)

    # --- Notificações (seção 20) — o que os robôs em background produzem ---

    def list_notifications(self, access_token: str, **params) -> dict:
        return self._list("notifications", access_token, **params)

    def mark_notification_read(self, access_token: str, notification_id: int) -> dict:
        return self._request("POST", f"/api/v1/notifications/{notification_id}/read", access_token=access_token)

    def mark_all_notifications_read(self, access_token: str) -> dict:
        return self._request("POST", "/api/v1/notifications/read-all", access_token=access_token)

    # --- Painel de operações / TV (link somente-leitura, sem login) ---

    def get_panel_token(self, access_token: str) -> dict:
        return self._request("GET", "/api/v1/panel/token", access_token=access_token)

    def regenerate_panel_token(self, access_token: str) -> dict:
        return self._request("POST", "/api/v1/panel/token/regenerate", access_token=access_token)

    # --- Relatórios (seção 17) ---

    def preview_report(self, access_token: str, report_type: str, **params) -> dict:
        return self._request(
            "GET", "/api/v1/reports/preview", params={"report_type": report_type, **params}, access_token=access_token,
        )

    def export_report(self, access_token: str, report_type: str, export_format: str, **params) -> bytes:
        """Diferente dos outros métodos: a resposta é o arquivo em si (bytes),
        não JSON — não passa por `_request`, que sempre espera JSON."""
        headers = {"Authorization": f"Bearer {access_token}"}
        clean_params = {
            k: v for k, v in {"report_type": report_type, "format": export_format, **params}.items()
            if v is not None and v != ""
        }
        try:
            response = self._client.request("GET", "/api/v1/reports/export", params=clean_params, headers=headers)
        except httpx.ConnectError as exc:
            raise ConnectionUnavailableError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise ApiError(
                "O servidor demorou demais para responder.\n\nTente novamente em instantes.",
                error_code="OF-API-002", technical_detail=str(exc),
            ) from exc
        except httpx.HTTPError as exc:
            raise ConnectionUnavailableError(str(exc)) from exc
        if response.status_code >= 400:
            raise _error_from_response(response)
        return response.content

    def _request(
        self, method: str, path: str, *, json: dict | None = None, params: dict | None = None,
        access_token: str | None = None, timeout: float = httpx.USE_CLIENT_DEFAULT,
    ) -> dict | list:
        # `timeout` deliberadamente NÃO tem `None` como default: pro próprio
        # httpx, passar `timeout=None` num request específico significa
        # "sem timeout nenhum" (infinito) — diferente de simplesmente não
        # passar o parâmetro (aí sim usa o timeout padrão do `Client`, ver
        # `config.request_timeout_seconds`). `USE_CLIENT_DEFAULT` é o
        # sentinel certo pra "não fui chamado com um valor específico".
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else None
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        try:
            response = self._client.request(
                method, path, json=json, params=clean_params or None, headers=headers, timeout=timeout,
            )
        except httpx.ConnectError as exc:
            raise ConnectionUnavailableError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise ApiError(
                "O servidor demorou demais para responder.\n\nTente novamente em instantes.",
                error_code="OF-API-002", technical_detail=str(exc),
            ) from exc
        except httpx.HTTPError as exc:
            raise ConnectionUnavailableError(str(exc)) from exc

        if response.status_code >= 400:
            raise _error_from_response(response)

        if response.status_code == 204 or not response.content:
            return {}
        return response.json()


def _error_from_response(response: httpx.Response) -> ApiError:
    try:
        payload = response.json()
        error = payload.get("error", {})
        message = error.get("message") or "Ocorreu um erro inesperado."
        code = error.get("code") or f"OF-API-{response.status_code}"
    except ValueError:
        message = "Ocorreu um erro inesperado."
        code = f"OF-API-{response.status_code}"
    logger.warning("Erro da API: %s %s — %s", response.status_code, code, message)
    return ApiError(message, error_code=code, technical_detail=response.text)
