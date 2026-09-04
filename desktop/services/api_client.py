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

    def _request(
        self, method: str, path: str, *, json: dict | None = None, params: dict | None = None,
        access_token: str | None = None,
    ) -> dict:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else None
        clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        try:
            response = self._client.request(method, path, json=json, params=clean_params or None, headers=headers)
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
