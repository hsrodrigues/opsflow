"""Friendly, user-facing API errors (seção 31).

Every screen that calls the API catches `ApiError` and shows
`friendly_message` to the user — never a raw exception/traceback. The
technical detail (if any) is only ever logged, never displayed.
"""


class ApiError(Exception):
    """A failure calling the OpsFlow API, already translated to a friendly message."""

    def __init__(self, friendly_message: str, *, error_code: str, technical_detail: str | None = None) -> None:
        self.friendly_message = friendly_message
        self.error_code = error_code
        self.technical_detail = technical_detail
        super().__init__(friendly_message)


class ConnectionUnavailableError(ApiError):
    """Raised when the server cannot be reached at all (seção 32: offline indicator)."""

    def __init__(self, technical_detail: str | None = None) -> None:
        super().__init__(
            "Não foi possível conectar ao servidor.\n\nVerifique sua conexão com a internet.",
            error_code="OF-API-001",
            technical_detail=technical_detail,
        )
