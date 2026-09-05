"""Duplicate-schedule dialog (seção 13, pedido explícito do cliente: reduzir
reentrada manual de rotas recorrentes — "poucos processos manuais"). Clona
toda a programação (todos os turnos) de uma data pra outra, via `POST
/api/v1/schedules/duplicate` (que por sua vez chama a stored procedure
`sp_duplicate_schedule_day`).
"""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDateEdit, QDialog, QFormLayout, QLabel, QVBoxLayout

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.widgets import build_dialog_buttons, build_dialog_header


class DuplicateScheduleDialog(QDialog):
    def __init__(self, api_client: ApiClient, access_token: str, *, source_date: QDate) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._worker: ApiWorker | None = None
        self.items_created: int | None = None

        self.setWindowTitle("Duplicar programação")
        self.setMinimumWidth(420)
        self._build_ui(source_date)

    def _build_ui(self, source_date: QDate) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        layout.addWidget(build_dialog_header(
            "📋", "IconChipInfo", "Duplicar programação",
            "Clona todos os turnos e itens de um dia pra outra data",
        ))
        layout.addSpacing(18)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        form = QFormLayout()
        form.setSpacing(10)

        self._source_input = QDateEdit()
        self._source_input.setCalendarPopup(True)
        self._source_input.setDisplayFormat("dd/MM/yyyy")
        self._source_input.setDate(source_date)
        form.addRow("Data de origem", self._source_input)

        self._target_input = QDateEdit()
        self._target_input.setCalendarPopup(True)
        self._target_input.setDisplayFormat("dd/MM/yyyy")
        self._target_input.setDate(source_date.addDays(7))
        form.addRow("Data de destino", self._target_input)

        layout.addLayout(form)
        layout.addSpacing(8)

        buttons = build_dialog_buttons("Duplicar")
        buttons.accepted.connect(self._handle_duplicate_clicked)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _handle_duplicate_clicked(self) -> None:
        source = self._source_input.date()
        target = self._target_input.date()
        if source == target:
            self._show_error("A data de destino precisa ser diferente da data de origem.")
            return

        self._buttons.setEnabled(False)
        self._worker = ApiWorker(
            self._api_client.duplicate_schedule, self._access_token,
            source.toString("yyyy-MM-dd"), target.toString("yyyy-MM-dd"),
        )
        self._worker.succeeded.connect(self._handle_duplicate_succeeded)
        self._worker.failed.connect(self._handle_duplicate_failed)
        self._worker.start()

    def _handle_duplicate_succeeded(self, result: dict) -> None:
        self.items_created = result["items_created"]
        self.accept()

    def _handle_duplicate_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível duplicar a programação."
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
