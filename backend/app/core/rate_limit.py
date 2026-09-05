"""Rate limiting (Fase 11 "Hardening de segurança").

`rate_limit_per_minute` existia em `Settings` desde a Fase 1 mas nunca foi
de fato aplicado em lugar nenhum — um valor de configuração que parecia
fazer algo e não fazia. Esta é a aplicação real: janela fixa de 1 minuto,
por IP de origem, em memória do próprio processo.

Em memória porque hoje só existe UM processo da API (nenhum multi-worker/
gunicorn ainda) — um contador compartilhado entre processos precisaria de
um armazenamento externo. Já há Redis reservado na arquitetura
(`docs/ARCHITECTURE.md`) exatamente para quando isso passar a ser
necessário; nada aqui impede migrar o contador pra lá depois, a interface
(`check` retornando permitido/negado) continua a mesma.
"""
import time
import uuid
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, requests_per_minute: int) -> None:
        super().__init__(app)
        self._limit = requests_per_minute
        self._lock = Lock()
        # client_ip -> (janela_atual_em_epoch_minutos, contagem_na_janela)
        self._windows: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_window = int(time.time() // 60)

        with self._lock:
            window, count = self._windows[client_ip]
            if window != current_window:
                window, count = current_window, 0
            count += 1
            self._windows[client_ip] = (window, count)
            # Poda oportunista: sem isso, `_windows` cresce sem limite pra
            # sempre (um IP novo por request nunca mais é esquecido).
            if len(self._windows) > 10_000:
                stale = [ip for ip, (w, _c) in self._windows.items() if w != current_window]
                for ip in stale:
                    del self._windows[ip]

        if count > self._limit:
            # Mesmo formato de erro de `app/core/exceptions.py`
            # (`_error_payload`) — não reaproveitado diretamente porque este
            # middleware roda fora do ciclo normal de exception handlers do
            # FastAPI, mas o cliente (`services/errors.py` no desktop) lê
            # `error.code`/`error.message` de qualquer resposta de erro,
            # então o formato precisa ser idêntico.
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "OF-API-429",
                        "message": "Muitas requisições em pouco tempo. Aguarde um instante e tente de novo.",
                        "request_id": str(uuid.uuid4()),
                    }
                },
            )
        return await call_next(request)
