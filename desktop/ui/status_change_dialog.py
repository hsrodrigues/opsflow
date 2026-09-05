"""Status-change dialog for a schedule item — the timeline of seção 13.

Shows the history of transitions so far and lets the user record the next
one; every change goes through `POST /schedules/items/{id}/status`, which is
also what turns the item into a live `Operation` the first time it leaves
`PROGRAMADO` (seção 21).
"""
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.widgets import build_dialog_buttons, build_dialog_header
from utils.formatting import format_datetime_br

_STATUS_OPTIONS = ["PROGRAMADO", "AGUARDANDO", "EM_FILA", "EM_OPERACAO", "CONCLUIDO", "ATRASADO", "CANCELADO"]
_STATUS_LABELS = {
    "PROGRAMADO": "Programado", "AGUARDANDO": "Aguardando", "EM_FILA": "Em fila",
    "EM_OPERACAO": "Em operação", "CONCLUIDO": "Concluído", "ATRASADO": "Atrasado", "CANCELADO": "Cancelado",
}


class StatusChangeDialog(QDialog):
    def __init__(self, api_client: ApiClient, access_token: str, item: dict) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._item = item
        self._worker: ApiWorker | None = None
        self._history_worker: ApiWorker | None = None
        self.saved_item: dict | None = None

        self.setWindowTitle(f"Alterar status — {item['route_name']}")
        self.setMinimumWidth(420)
        self._build_ui()
        self._load_history()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        layout.addWidget(build_dialog_header(
            "🔄", "IconChipInfo", "Alterar status", self._item["route_name"],
        ))
        layout.addSpacing(18)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        layout.addWidget(QLabel("Linha do tempo", objectName="SectionTitle"))
        self._history_label = QLabel("Carregando...")
        self._history_label.setObjectName("Muted")
        self._history_label.setWordWrap(True)
        layout.addWidget(self._history_label)
        layout.addSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self._status_combo = QComboBox()
        for status in _STATUS_OPTIONS:
            self._status_combo.addItem(_STATUS_LABELS[status], status)
        current_index = self._status_combo.findData(self._item["status"])
        if current_index >= 0:
            self._status_combo.setCurrentIndex(current_index)
        form.addRow("Novo status", self._status_combo)

        self._notes_input = QTextEdit()
        self._notes_input.setFixedHeight(60)
        form.addRow("Observações", self._notes_input)

        layout.addLayout(form)
        layout.addSpacing(8)

        buttons = build_dialog_buttons("Confirmar")
        buttons.accepted.connect(self._handle_confirm_clicked)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _load_history(self) -> None:
        self._history_worker = ApiWorker(
            self._api_client.get_schedule_item_history, self._access_token, self._item["id"]
        )
        self._history_worker.succeeded.connect(self._handle_history_loaded)
        self._history_worker.failed.connect(lambda _exc: self._history_label.setText("—"))
        self._history_worker.start()

    def _handle_history_loaded(self, history: list) -> None:
        if not history:
            self._history_label.setText("Ainda programado — nenhuma execução registrada.")
            return
        lines = []
        for entry in history:
            time_text = format_datetime_br(entry["changed_at"])
            label = _STATUS_LABELS.get(entry["new_status"], entry["new_status"])
            lines.append(f"{time_text}  →  {label}" + (f" ({entry['notes']})" if entry.get("notes") else ""))
        self._history_label.setText("\n".join(lines))

    def _handle_confirm_clicked(self) -> None:
        new_status = self._status_combo.currentData()
        notes = self._notes_input.toPlainText().strip() or None

        self._buttons.setEnabled(False)
        self._worker = ApiWorker(
            self._api_client.change_schedule_item_status, self._access_token, self._item["id"], new_status, notes,
        )
        self._worker.succeeded.connect(self._handle_change_succeeded)
        self._worker.failed.connect(self._handle_change_failed)
        self._worker.start()

    def _handle_change_succeeded(self, result: dict) -> None:
        self.saved_item = result
        self.accept()

    def _handle_change_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível alterar o status."
        self._error_label.setText(message)
        self._error_label.show()
