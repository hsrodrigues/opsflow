"""Create/edit dialog for a route (seção 12)."""
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.widgets import build_dialog_buttons, build_dialog_header

_STATUS_OPTIONS = ["ATIVA", "INATIVA"]
_OPERATION_TYPES = ["", "ENTREGA", "COLETA", "TRANSFERENCIA"]

# Sentinela "não informado": um pouco abaixo do mínimo geográfico real
# (-90/-180), com `setSpecialValueText` mostrando um traço em vez do número
# nesse valor — assim dá pra distinguir "usuário não preencheu" de "0.0"
# (que é uma coordenada real, o cruzamento do equador com Greenwich) sem
# precisar de um checkbox "tem coordenada?" a mais no formulário.
_LAT_UNSET, _LNG_UNSET = -91.0, -181.0


def _coord_spinbox(minimum: float, maximum: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(6)
    spin.setSpecialValueText("— (opcional)")
    spin.setValue(minimum)
    return spin


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
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        layout.addWidget(build_dialog_header(
            "🗺️", "IconChipInfo",
            "Editar rota" if self._route else "Nova rota",
            "Origem, destino e tempo estimado do trajeto",
        ))
        layout.addSpacing(18)

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

        # Opcionais — só existem para desenhar a rota no mapa do Painel de
        # operações (TV); nada mais no sistema depende delas.
        origin_coords_row = QHBoxLayout()
        self._origin_lat_input = _coord_spinbox(_LAT_UNSET, 90)
        self._origin_lng_input = _coord_spinbox(_LNG_UNSET, 180)
        origin_coords_row.addWidget(self._origin_lat_input)
        origin_coords_row.addWidget(self._origin_lng_input)
        form.addRow("Coord. origem (lat/long)", origin_coords_row)

        destination_coords_row = QHBoxLayout()
        self._destination_lat_input = _coord_spinbox(_LAT_UNSET, 90)
        self._destination_lng_input = _coord_spinbox(_LNG_UNSET, 180)
        destination_coords_row.addWidget(self._destination_lat_input)
        destination_coords_row.addWidget(self._destination_lng_input)
        form.addRow("Coord. destino (lat/long)", destination_coords_row)

        self._distance_input = QDoubleSpinBox()
        self._distance_input.setRange(0, 100_000)
        self._distance_input.setDecimals(1)
        self._distance_input.setSuffix(" km")
        form.addRow("Distância", self._distance_input)

        # Horas + minutos em vez de exigir a conta manual em minutos — o
        # backend continua guardando um total em minutos (`estimated_time_
        # minutes`), a conversão pros dois campos e de volta é toda daqui.
        time_row = QHBoxLayout()
        self._time_hours_input = QSpinBox()
        self._time_hours_input.setRange(0, 999)
        self._time_hours_input.setSuffix(" h")
        time_row.addWidget(self._time_hours_input)
        self._time_minutes_input = QSpinBox()
        self._time_minutes_input.setRange(0, 59)
        self._time_minutes_input.setSuffix(" min")
        time_row.addWidget(self._time_minutes_input)
        time_row.addStretch(1)
        form.addRow("Tempo estimado", time_row)

        self._operation_type_combo = QComboBox()
        self._operation_type_combo.addItems(_OPERATION_TYPES)
        form.addRow("Tipo de operação", self._operation_type_combo)

        self._status_combo = QComboBox()
        self._status_combo.addItems(_STATUS_OPTIONS)
        self._status_combo.setEnabled(self._route is not None)
        form.addRow("Status", self._status_combo)

        layout.addLayout(form)
        layout.addSpacing(8)

        buttons = build_dialog_buttons("Salvar")
        buttons.accepted.connect(self._handle_save_clicked)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _fill_from_route(self, route: dict) -> None:
        self._name_input.setText(route["name"])
        self._origin_input.setText(route["origin_name"])
        self._destination_input.setText(route["destination_name"])
        if route.get("origin_latitude") is not None:
            self._origin_lat_input.setValue(route["origin_latitude"])
            self._origin_lng_input.setValue(route["origin_longitude"])
        if route.get("destination_latitude") is not None:
            self._destination_lat_input.setValue(route["destination_latitude"])
            self._destination_lng_input.setValue(route["destination_longitude"])
        self._distance_input.setValue(route.get("distance_km") or 0)
        hours, minutes = divmod(route.get("estimated_time_minutes") or 0, 60)
        self._time_hours_input.setValue(hours)
        self._time_minutes_input.setValue(minutes)
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

        total_minutes = self._time_hours_input.value() * 60 + self._time_minutes_input.value()
        origin_lat = self._origin_lat_input.value()
        origin_lng = self._origin_lng_input.value()
        destination_lat = self._destination_lat_input.value()
        destination_lng = self._destination_lng_input.value()
        payload = {
            "name": name,
            "origin_name": origin,
            "destination_name": destination,
            "origin_latitude": origin_lat if origin_lat > _LAT_UNSET else None,
            "origin_longitude": origin_lng if origin_lng > _LNG_UNSET else None,
            "destination_latitude": destination_lat if destination_lat > _LAT_UNSET else None,
            "destination_longitude": destination_lng if destination_lng > _LNG_UNSET else None,
            "distance_km": self._distance_input.value() or None,
            "estimated_time_minutes": total_minutes or None,
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
