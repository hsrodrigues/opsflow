"""Create/edit dialog for an occurrence (seção 14)."""
from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
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

_TYPE_SUGGESTIONS = [
    "Atraso", "Quebra", "Acidente", "Falta de documentação", "Problema operacional",
    "Indisponibilidade", "Excesso de tempo", "Cancelamento", "Divergência", "Outros",
]
_SEVERITY_OPTIONS = ["BAIXA", "MEDIA", "ALTA", "CRITICA"]
_SEVERITY_LABELS = {"BAIXA": "Baixa", "MEDIA": "Média", "ALTA": "Alta", "CRITICA": "Crítica"}
_STATUS_OPTIONS = ["ABERTA", "EM_ANALISE", "RESOLVIDA", "CANCELADA"]
_STATUS_LABELS = {"ABERTA": "Aberta", "EM_ANALISE": "Em análise", "RESOLVIDA": "Resolvida", "CANCELADA": "Cancelada"}


class OccurrenceDialog(QDialog):
    def __init__(
        self, api_client: ApiClient, access_token: str, vehicles: list[dict], drivers: list[dict],
        occurrence: dict | None = None,
    ) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._vehicles = vehicles
        self._drivers = drivers
        self._occurrence = occurrence
        self._worker: ApiWorker | None = None
        self.saved_occurrence: dict | None = None

        self.setWindowTitle("Editar ocorrência" if occurrence else "Nova ocorrência")
        self.setMinimumWidth(440)
        self._build_ui()
        if occurrence:
            self._fill_from_occurrence(occurrence)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        layout.addWidget(build_dialog_header(
            "⚠️", "IconChipWarning",
            "Editar ocorrência" if self._occurrence else "Nova ocorrência",
            "Registro do evento e vínculo com veículo/motorista",
        ))
        layout.addSpacing(18)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        form = QFormLayout()
        form.setSpacing(10)

        self._type_combo = QComboBox()
        self._type_combo.setEditable(True)
        self._type_combo.addItems(_TYPE_SUGGESTIONS)
        form.addRow("Tipo *", self._type_combo)

        self._occurred_at_input = QDateTimeEdit()
        self._occurred_at_input.setCalendarPopup(True)
        self._occurred_at_input.setDisplayFormat("dd/MM/yyyy HH:mm")
        self._occurred_at_input.setDateTime(QDateTime.currentDateTime())
        form.addRow("Data/Hora *", self._occurred_at_input)

        self._vehicle_combo = QComboBox()
        self._vehicle_combo.addItem("— Sem veículo —", None)
        for vehicle in self._vehicles:
            self._vehicle_combo.addItem(vehicle["plate"], vehicle["id"])
        form.addRow("Veículo", self._vehicle_combo)

        self._driver_combo = QComboBox()
        self._driver_combo.addItem("— Sem motorista —", None)
        for driver in self._drivers:
            self._driver_combo.addItem(driver["full_name"], driver["id"])
        form.addRow("Motorista", self._driver_combo)

        self._severity_combo = QComboBox()
        for severity in _SEVERITY_OPTIONS:
            self._severity_combo.addItem(_SEVERITY_LABELS[severity], severity)
        form.addRow("Severidade", self._severity_combo)

        self._status_combo = QComboBox()
        for status in _STATUS_OPTIONS:
            self._status_combo.addItem(_STATUS_LABELS[status], status)
        self._status_combo.setEnabled(self._occurrence is not None)
        form.addRow("Status", self._status_combo)

        self._description_input = QTextEdit()
        self._description_input.setFixedHeight(80)
        form.addRow("Descrição *", self._description_input)

        layout.addLayout(form)
        layout.addSpacing(8)

        buttons = build_dialog_buttons("Salvar")
        buttons.accepted.connect(self._handle_save_clicked)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _fill_from_occurrence(self, occurrence: dict) -> None:
        self._type_combo.setCurrentText(occurrence["occurrence_type_name"])
        self._occurred_at_input.setDateTime(QDateTime.fromString(occurrence["occurred_at"], "yyyy-MM-ddTHH:mm:ss"))
        if occurrence.get("vehicle_plate"):
            index = self._vehicle_combo.findText(occurrence["vehicle_plate"])
            if index >= 0:
                self._vehicle_combo.setCurrentIndex(index)
        if occurrence.get("driver_name"):
            index = self._driver_combo.findText(occurrence["driver_name"])
            if index >= 0:
                self._driver_combo.setCurrentIndex(index)
        severity_index = self._severity_combo.findData(occurrence.get("severity", "BAIXA"))
        if severity_index >= 0:
            self._severity_combo.setCurrentIndex(severity_index)
        status_index = self._status_combo.findData(occurrence.get("status", "ABERTA"))
        if status_index >= 0:
            self._status_combo.setCurrentIndex(status_index)
        self._description_input.setPlainText(occurrence.get("description") or "")

    def _handle_save_clicked(self) -> None:
        type_name = self._type_combo.currentText().strip()
        description = self._description_input.toPlainText().strip()
        if not type_name or not description:
            self._show_error("Informe o tipo e a descrição da ocorrência.")
            return

        payload = {
            "occurrence_type_name": type_name,
            "vehicle_id": self._vehicle_combo.currentData(),
            "driver_id": self._driver_combo.currentData(),
            "description": description,
            "severity": self._severity_combo.currentData(),
            "occurred_at": self._occurred_at_input.dateTime().toString("yyyy-MM-ddTHH:mm:ss"),
        }
        if self._occurrence is not None:
            payload["status"] = self._status_combo.currentData()

        self._buttons.setEnabled(False)
        if self._occurrence is None:
            self._worker = ApiWorker(self._api_client.create_occurrence, self._access_token, payload)
        else:
            self._worker = ApiWorker(
                self._api_client.update_occurrence, self._access_token, self._occurrence["id"], payload
            )
        self._worker.succeeded.connect(self._handle_save_succeeded)
        self._worker.failed.connect(self._handle_save_failed)
        self._worker.start()

    def _handle_save_succeeded(self, result: dict) -> None:
        self.saved_occurrence = result
        self.accept()

    def _handle_save_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível salvar a ocorrência."
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
