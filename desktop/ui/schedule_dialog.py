"""Create/edit dialog for a schedule item — programação (seção 13)."""
from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError

_SHIFT_OPTIONS = ["MANHA", "TARDE", "NOITE"]
_SHIFT_LABELS = {"MANHA": "Manhã", "TARDE": "Tarde", "NOITE": "Noite"}


class ScheduleItemDialog(QDialog):
    """Modal form to create a new programação or edit an existing one's details.

    Status changes go through `StatusChangeDialog` instead — a programação's
    lifecycle is a deliberate action, not a field you edit inline.
    """

    def __init__(
        self, api_client: ApiClient, access_token: str, routes: list[dict], carriers: list[dict],
        vehicles: list[dict], drivers: list[dict], item: dict | None = None,
    ) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._routes = routes
        self._carriers = carriers
        self._vehicles = vehicles
        self._drivers = drivers
        self._item = item
        self._worker: ApiWorker | None = None
        self.saved_item: dict | None = None

        self.setWindowTitle("Editar programação" if item else "Nova programação")
        self.setMinimumWidth(440)
        self._build_ui()
        if item:
            self._fill_from_item(item)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        form = QFormLayout()
        form.setSpacing(10)

        self._route_combo = QComboBox()
        for route in self._routes:
            self._route_combo.addItem(f"{route['name']}", route["id"])
        form.addRow("Rota *", self._route_combo)

        self._shift_combo = QComboBox()
        for shift in _SHIFT_OPTIONS:
            self._shift_combo.addItem(_SHIFT_LABELS[shift], shift)
        form.addRow("Turno *", self._shift_combo)

        self._scheduled_at_input = QDateTimeEdit()
        self._scheduled_at_input.setCalendarPopup(True)
        self._scheduled_at_input.setDisplayFormat("dd/MM/yyyy HH:mm")
        self._scheduled_at_input.setDateTime(QDateTime.currentDateTime())
        form.addRow("Horário previsto *", self._scheduled_at_input)

        self._carrier_combo = QComboBox()
        self._carrier_combo.addItem("— Sem transportadora —", None)
        for carrier in self._carriers:
            self._carrier_combo.addItem(carrier["legal_name"], carrier["id"])
        form.addRow("Transportadora", self._carrier_combo)

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

        self._cargo_input = QLineEdit()
        form.addRow("Carga", self._cargo_input)

        self._quantity_input = QSpinBox()
        self._quantity_input.setRange(0, 1_000_000)
        form.addRow("Quantidade", self._quantity_input)

        self._notes_input = QTextEdit()
        self._notes_input.setFixedHeight(70)
        form.addRow("Observações", self._notes_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("PrimaryButton")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("SecondaryButton")
        buttons.accepted.connect(self._handle_save_clicked)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _fill_from_item(self, item: dict) -> None:
        route_index = self._route_combo.findText(item["route_name"])
        if route_index >= 0:
            self._route_combo.setCurrentIndex(route_index)
        shift_index = self._shift_combo.findData(item["shift"])
        if shift_index >= 0:
            self._shift_combo.setCurrentIndex(shift_index)
        self._scheduled_at_input.setDateTime(QDateTime.fromString(item["scheduled_at"], "yyyy-MM-ddTHH:mm:ss"))
        if item.get("carrier_name"):
            index = self._carrier_combo.findText(item["carrier_name"])
            if index >= 0:
                self._carrier_combo.setCurrentIndex(index)
        if item.get("vehicle_plate"):
            index = self._vehicle_combo.findText(item["vehicle_plate"])
            if index >= 0:
                self._vehicle_combo.setCurrentIndex(index)
        if item.get("driver_name"):
            index = self._driver_combo.findText(item["driver_name"])
            if index >= 0:
                self._driver_combo.setCurrentIndex(index)
        self._cargo_input.setText(item.get("cargo_description") or "")
        self._quantity_input.setValue(int(item.get("quantity") or 0))
        self._notes_input.setPlainText(item.get("notes") or "")
        # Só se altera dados de planejamento pré-execução: mudar rota/veículo já em operação é feito
        # de outro jeito (esta tela não decide isso, só desabilita para não confundir o usuário aqui).
        is_editable = item["status"] == "PROGRAMADO"
        for widget in (self._route_combo, self._carrier_combo, self._vehicle_combo, self._driver_combo):
            widget.setEnabled(is_editable)

    def _handle_save_clicked(self) -> None:
        if self._route_combo.count() == 0:
            self._show_error("Cadastre ao menos uma rota antes de criar uma programação.")
            return

        scheduled_dt = self._scheduled_at_input.dateTime()
        payload = {
            "route_id": self._route_combo.currentData(),
            "carrier_id": self._carrier_combo.currentData(),
            "vehicle_id": self._vehicle_combo.currentData(),
            "driver_id": self._driver_combo.currentData(),
            "scheduled_at": scheduled_dt.toString("yyyy-MM-ddTHH:mm:ss"),
            "cargo_description": self._cargo_input.text().strip() or None,
            "quantity": self._quantity_input.value() or None,
            "notes": self._notes_input.toPlainText().strip() or None,
        }
        if self._item is None:
            payload["schedule_date"] = scheduled_dt.date().toString("yyyy-MM-dd")
            payload["shift"] = self._shift_combo.currentData()

        self._buttons.setEnabled(False)
        if self._item is None:
            self._worker = ApiWorker(self._api_client.create_schedule_item, self._access_token, payload)
        else:
            self._worker = ApiWorker(
                self._api_client.update_schedule_item, self._access_token, self._item["id"], payload
            )
        self._worker.succeeded.connect(self._handle_save_succeeded)
        self._worker.failed.connect(self._handle_save_failed)
        self._worker.start()

    def _handle_save_succeeded(self, result: dict) -> None:
        self.saved_item = result
        self.accept()

    def _handle_save_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível salvar a programação."
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
