"""Application-wide exception hierarchy and FastAPI error handlers.

Every exception raised by the domain/service layer should be one of the
`OpsFlowError` subclasses below. The registered handlers turn them into a
consistent JSON payload with a friendly message and a stable error code
(e.g. "OF-API-001"), while the full technical detail is always sent to the
error log — never to the client.
"""
import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class OpsFlowError(Exception):
    """Base class for all handled application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "OF-API-000"
    friendly_message: str = "Ocorreu um erro inesperado."

    def __init__(self, friendly_message: str | None = None, *, technical_detail: str | None = None) -> None:
        self.friendly_message = friendly_message or self.friendly_message
        self.technical_detail = technical_detail
        super().__init__(self.friendly_message)


class NotFoundError(OpsFlowError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "OF-API-404"
    friendly_message = "Registro não encontrado."


class ValidationFailedError(OpsFlowError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "OF-API-422"
    friendly_message = "Os dados informados são inválidos."


class UnauthorizedError(OpsFlowError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "OF-API-401"
    friendly_message = "Não foi possível autenticar. Faça login novamente."


class ForbiddenError(OpsFlowError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "OF-API-403"
    friendly_message = "Você não tem permissão para executar esta ação."


class ConflictError(OpsFlowError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "OF-API-409"
    friendly_message = "Este registro já existe ou está em conflito com outro."


class LicenseError(OpsFlowError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    error_code = "OF-API-402"
    friendly_message = "Licença inválida, expirada ou com limite excedido."


class DatabaseUnavailableError(OpsFlowError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "OF-API-001"
    friendly_message = "Não foi possível conectar ao servidor. Verifique sua conexão com a internet."


def _error_payload(error_code: str, message: str, request_id: str) -> dict:
    return {
        "error": {
            "code": error_code,
            "message": message,
            "request_id": request_id,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers to the FastAPI application."""

    @app.exception_handler(OpsFlowError)
    async def handle_opsflow_error(request: Request, exc: OpsFlowError) -> JSONResponse:
        request_id = str(uuid.uuid4())
        logger.error(
            "OpsFlowError %s on %s %s (request_id=%s): %s",
            exc.error_code,
            request.method,
            request.url.path,
            request_id,
            exc.technical_detail or str(exc),
            exc_info=exc if exc.technical_detail is None else None,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(exc.error_code, exc.friendly_message, request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = str(uuid.uuid4())
        logger.warning(
            "Validation error on %s %s (request_id=%s): %s",
            request.method,
            request.url.path,
            request_id,
            exc.errors(),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_payload("OF-API-422", "Os dados informados são inválidos.", request_id),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = str(uuid.uuid4())
        logger.exception(
            "Unhandled exception on %s %s (request_id=%s)",
            request.method,
            request.url.path,
            request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload("OF-API-500", "Ocorreu um erro inesperado no servidor.", request_id),
        )
