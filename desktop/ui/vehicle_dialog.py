"""Create/edit dialog for a vehicle (seção 9: "edição")."""
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError

_STATUS_OPTIONS = ["DISPONIVEL", "EM_OPERACAO", "EM_MANUTENCAO", "INATIVO", "BLOQUEADO"]


class VehicleDialog(QDialog):
    """Modal form to create a new vehicle or edit an existing one.

    `vehicle` is `None` for "new vehicle"; otherwise the dict returned by
    the list/get endpoint, pre-filling every field.
    """

    def __init__(self, api_client: ApiClient, access_token: str, carriers: list[dict], vehicle: dict | None = None) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._carriers = carriers
        self._vehicle = vehicle
        self._worker: ApiWorker | None = None
        self.saved_vehicle: dict | None = None

        self.setWindowTitle("Editar veículo" if vehicle else "Novo veículo")
        self.setMinimumWidth(420)
        self._build_ui()
        if vehicle:
            self._fill_from_vehicle(vehicle)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        form = QFormLayout()
        form.setSpacing(10)

        self._plate_input = QLineEdit()
        self._plate_input.setMaxLength(10)
        form.addRow("Placa *", self._plate_input)

        self._brand_input = QLineEdit()
        form.addRow("Marca", self._brand_input)

        self._model_input = QLineEdit()
        form.addRow("Modelo", self._model_input)

        self._year_input = QSpinBox()
        self._year_input.setRange(0, 2100)
        self._year_input.setSpecialValueText("—")
        form.addRow("Ano", self._year_input)

        self._capacity_input = QDoubleSpinBox()
        self._capacity_input.setRange(0, 1_000_000)
        self._capacity_input.setDecimals(2)
        self._capacity_input.setSuffix(" kg")
        form.addRow("Capacidade", self._capacity_input)

        self._carrier_combo = QComboBox()
        self._carrier_combo.addItem("— Sem transportadora —", None)
        for carrier in self._carriers:
            self._carrier_combo.addItem(carrier["legal_name"], carrier["id"])
        form.addRow("Transportadora", self._carrier_combo)

        self._status_combo = QComboBox()
        self._status_combo.addItems(_STATUS_OPTIONS)
        self._status_combo.setEnabled(self._vehicle is not None)  # só faz sentido escolher ao editar
        form.addRow("Status", self._status_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("PrimaryButton")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._handle_save_clicked)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _fill_from_vehicle(self, vehicle: dict) -> None:
        self._plate_input.setText(vehicle["plate"])
        self._brand_input.setText(vehicle.get("brand") or "")
        self._model_input.setText(vehicle.get("model") or "")
        self._year_input.setValue(vehicle.get("year") or 0)
        self._capacity_input.setValue(vehicle.get("capacity") or 0)
        if vehicle.get("carrier_id") is not None:
            index = self._carrier_combo.findData(vehicle["carrier_id"])
            if index >= 0:
                self._carrier_combo.setCurrentIndex(index)
        status_index = self._status_combo.findText(vehicle.get("status", "DISPONIVEL"))
        if status_index >= 0:
            self._status_combo.setCurrentIndex(status_index)

    def _handle_save_clicked(self) -> None:
        plate = self._plate_input.text().strip().upper()
        if not plate:
            self._show_error("Informe a placa do veículo.")
            return

        payload = {
            "plate": plate,
            "brand": self._brand_input.text().strip() or None,
            "model": self._model_input.text().strip() or None,
            "year": self._year_input.value() or None,
            "capacity": self._capacity_input.value() or None,
            "carrier_id": self._carrier_combo.currentData(),
        }
        if self._vehicle is not None:
            payload["status"] = self._status_combo.currentText()

        self._buttons.setEnabled(False)
        if self._vehicle is None:
            self._worker = ApiWorker(self._api_client.create_vehicle, self._access_token, payload)
        else:
            self._worker = ApiWorker(
                self._api_client.update_vehicle, self._access_token, self._vehicle["id"], payload
            )
        self._worker.succeeded.connect(self._handle_save_succeeded)
        self._worker.failed.connect(self._handle_save_failed)
        self._worker.start()

    def _handle_save_succeeded(self, result: dict) -> None:
        self.saved_vehicle = result
        self.accept()

    def _handle_save_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível salvar o veículo."
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
