"""Create/edit dialog for a route (seção 12)."""
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

_STATUS_OPTIONS = ["ATIVA", "INATIVA"]
_OPERATION_TYPES = ["", "ENTREGA", "COLETA", "TRANSFERENCIA"]


class RouteDialog(QDialog):
    """Modal form to create a new route or edit an existing one."""

    def __init__(self, api_client: ApiClient, access_token: str, route: dict | None = None) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._route = route
        self._worker: ApiWorker | None = None
        self.saved_route: dict | None = None

        self.setWindowTitle("Editar rota" if route else "Nova rota")
        self.setMinimumWidth(420)
        self._build_ui()
        if route:
            self._fill_from_route(route)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Ex.: São Paulo → Campinas")
        form.addRow("Nome da rota *", self._name_input)

        self._origin_input = QLineEdit()
        form.addRow("Origem *", self._origin_input)

        self._destination_input = QLineEdit()
        form.addRow("Destino *", self._destination_input)

        self._distance_input = QDoubleSpinBox()
        self._distance_input.setRange(0, 100_000)
        self._distance_input.setDecimals(1)
        self._distance_input.setSuffix(" km")
        form.addRow("Distância", self._distance_input)

        self._time_input = QSpinBox()
        self._time_input.setRange(0, 100_000)
        self._time_input.setSuffix(" min")
        form.addRow("Tempo estimado", self._time_input)

        self._operation_type_combo = QComboBox()
        self._operation_type_combo.addItems(_OPERATION_TYPES)
        form.addRow("Tipo de operação", self._operation_type_combo)

        self._status_combo = QComboBox()
        self._status_combo.addItems(_STATUS_OPTIONS)
        self._status_combo.setEnabled(self._route is not None)
        form.addRow("Status", self._status_combo)

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

    def _fill_from_route(self, route: dict) -> None:
        self._name_input.setText(route["name"])
        self._origin_input.setText(route["origin_name"])
        self._destination_input.setText(route["destination_name"])
        self._distance_input.setValue(route.get("distance_km") or 0)
        self._time_input.setValue(route.get("estimated_time_minutes") or 0)
        if route.get("operation_type"):
            index = self._operation_type_combo.findText(route["operation_type"])
            if index >= 0:
                self._operation_type_combo.setCurrentIndex(index)
        status_index = self._status_combo.findText(route.get("status", "ATIVA"))
        if status_index >= 0:
            self._status_combo.setCurrentIndex(status_index)

    def _handle_save_clicked(self) -> None:
        name = self._name_input.text().strip()
        origin = self._origin_input.text().strip()
        destination = self._destination_input.text().strip()
        if not name or not origin or not destination:
            self._show_error("Informe nome, origem e destino da rota.")
            return

        payload = {
            "name": name,
            "origin_name": origin,
            "destination_name": destination,
            "distance_km": self._distance_input.value() or None,
            "estimated_time_minutes": self._time_input.value() or None,
            "operation_type": self._operation_type_combo.currentText() or None,
        }
        if self._route is not None:
            payload["status"] = self._status_combo.currentText()

        self._buttons.setEnabled(False)
        if self._route is None:
            self._worker = ApiWorker(self._api_client.create_route, self._access_token, payload)
        else:
            self._worker = ApiWorker(self._api_client.update_route, self._access_token, self._route["id"], payload)
        self._worker.succeeded.connect(self._handle_save_succeeded)
        self._worker.failed.connect(self._handle_save_failed)
        self._worker.start()

    def _handle_save_succeeded(self, result: dict) -> None:
        self.saved_route = result
        self.accept()

    def _handle_save_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível salvar a rota."
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
