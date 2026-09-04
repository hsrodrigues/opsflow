"""Vehicles screen (seção 9): pesquisa, filtros, paginação, edição, exclusão."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.vehicle_dialog import VehicleDialog

_STATUS_FILTER_OPTIONS = [
    ("Todos os status", None),
    ("Disponível", "DISPONIVEL"),
    ("Em operação", "EM_OPERACAO"),
    ("Em manutenção", "EM_MANUTENCAO"),
    ("Inativo", "INATIVO"),
    ("Bloqueado", "BLOQUEADO"),
]

_STATUS_DISPLAY = {
    "DISPONIVEL": "🟢 Disponível", "EM_OPERACAO": "🔵 Em operação", "EM_MANUTENCAO": "🟡 Em manutenção",
    "INATIVO": "⚪ Inativo", "BLOQUEADO": "🔴 Bloqueado",
}

_PAGE_SIZE = 15


class VehiclesPage(QWidget):
    def __init__(self, api_client: ApiClient, session: UserSession) -> None:
        super().__init__()
        self._api_client = api_client
        self._session = session
        self._page = 1
        self._total_pages = 1
        self._carriers_by_id: dict[int, str] = {}
        self._carriers_raw: list[dict] = []
        self._worker: ApiWorker | None = None
        self._dialog_worker: ApiWorker | None = None

        self._build_ui()
        self._load_carriers_then_vehicles()

    # --- UI ---

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(QLabel("Veículos", objectName="PageTitle"))
        header.addStretch(1)
        new_button = QPushButton("+ Novo Veículo", objectName="PrimaryButton")
        new_button.clicked.connect(self._handle_new_clicked)
        header.addWidget(new_button)
        layout.addLayout(header)

        toolbar = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Buscar por placa, marca ou modelo...")
        self._search_input.returnPressed.connect(self._handle_search)
        toolbar.addWidget(self._search_input, stretch=1)

        self._status_filter = QComboBox()
        for label, _value in _STATUS_FILTER_OPTIONS:
            self._status_filter.addItem(label)
        self._status_filter.currentIndexChanged.connect(self._handle_search)
        toolbar.addWidget(self._status_filter)

        search_button = QPushButton("Buscar", objectName="LinkButton")
        search_button.clicked.connect(self._handle_search)
        toolbar.addWidget(search_button)
        layout.addLayout(toolbar)

        self._status_message = QLabel("")
        self._status_message.setObjectName("Muted")
        self._status_message.hide()
        layout.addWidget(self._status_message)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["Placa", "Marca / Modelo", "Ano", "Transportadora", "Status", ""])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setMinimumSectionSize(120)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table, stretch=1)

        pagination = QHBoxLayout()
        self._page_label = QLabel("")
        self._page_label.setObjectName("Muted")
        pagination.addWidget(self._page_label)
        pagination.addStretch(1)
        self._prev_button = QPushButton("‹ Anterior", objectName="LinkButton")
        self._prev_button.clicked.connect(self._go_previous_page)
        self._next_button = QPushButton("Próxima ›", objectName="LinkButton")
        self._next_button.clicked.connect(self._go_next_page)
        pagination.addWidget(self._prev_button)
        pagination.addWidget(self._next_button)
        layout.addLayout(pagination)

    # --- carregamento de dados ---

    def _load_carriers_then_vehicles(self) -> None:
        worker = ApiWorker(self._api_client.list_carriers, self._session.access_token, page_size=100)
        worker.succeeded.connect(self._handle_carriers_loaded)
        worker.failed.connect(lambda _exc: self._load_vehicles())  # sem transportadoras, segue mesmo assim
        worker.start()
        self._carriers_worker = worker

    def _handle_carriers_loaded(self, result: dict) -> None:
        self._carriers_raw = result.get("items", [])
        self._carriers_by_id = {c["id"]: c["legal_name"] for c in self._carriers_raw}
        self._load_vehicles()

    def _handle_search(self) -> None:
        self._page = 1
        self._load_vehicles()

    def _go_previous_page(self) -> None:
        if self._page > 1:
            self._page -= 1
            self._load_vehicles()

    def _go_next_page(self) -> None:
        if self._page < self._total_pages:
            self._page += 1
            self._load_vehicles()

    def _load_vehicles(self) -> None:
        status_value = _STATUS_FILTER_OPTIONS[self._status_filter.currentIndex()][1]
        self._worker = ApiWorker(
            self._api_client.list_vehicles, self._session.access_token,
            q=self._search_input.text().strip() or None, status=status_value, page=self._page, page_size=_PAGE_SIZE,
        )
        self._worker.succeeded.connect(self._handle_vehicles_loaded)
        self._worker.failed.connect(self._handle_load_failed)
        self._worker.start()

    def _handle_vehicles_loaded(self, result: dict) -> None:
        items = result["items"]
        meta = result["meta"]
        self._total_pages = meta["total_pages"]
        self._page = meta["page"]

        self._table.setRowCount(0)
        for row, vehicle in enumerate(items):
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(vehicle["plate"]))
            brand_model = " / ".join(filter(None, [vehicle.get("brand"), vehicle.get("model")])) or "—"
            self._table.setItem(row, 1, QTableWidgetItem(brand_model))
            self._table.setItem(row, 2, QTableWidgetItem(str(vehicle.get("year") or "—")))
            carrier_name = self._carriers_by_id.get(vehicle.get("carrier_id"), "—")
            self._table.setItem(row, 3, QTableWidgetItem(carrier_name))
            status_item = QTableWidgetItem(_STATUS_DISPLAY.get(vehicle["status"], vehicle["status"]))
            self._table.setItem(row, 4, status_item)
            self._table.setCellWidget(row, 5, self._build_row_actions(vehicle))

        self._page_label.setText(
            f"Página {meta['page']} de {meta['total_pages']} — {meta['total']} veículo(s)"
        )
        self._prev_button.setEnabled(self._page > 1)
        self._next_button.setEnabled(self._page < self._total_pages)

    def _handle_load_failed(self, exc: Exception) -> None:
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível carregar os veículos."
        self._show_status(message, is_error=True)

    def _build_row_actions(self, vehicle: dict) -> QWidget:
        container = QWidget()
        row_layout = QHBoxLayout(container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        edit_button = QPushButton("Editar", objectName="LinkButton")
        edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_button.clicked.connect(lambda: self._handle_edit_clicked(vehicle))
        delete_button = QPushButton("Excluir", objectName="LinkButton")
        delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_button.clicked.connect(lambda: self._handle_delete_clicked(vehicle))
        row_layout.addWidget(edit_button)
        row_layout.addWidget(delete_button)
        row_layout.addStretch(1)
        return container

    # --- ações ---

    def _handle_new_clicked(self) -> None:
        dialog = VehicleDialog(self._api_client, self._session.access_token, self._carriers_raw)
        if dialog.exec():
            self._show_status(f"Veículo {dialog.saved_vehicle['plate']} criado com sucesso.")
            self._load_vehicles()

    def _handle_edit_clicked(self, vehicle: dict) -> None:
        dialog = VehicleDialog(self._api_client, self._session.access_token, self._carriers_raw, vehicle=vehicle)
        if dialog.exec():
            self._show_status(f"Veículo {dialog.saved_vehicle['plate']} atualizado com sucesso.")
            self._load_vehicles()

    def _handle_delete_clicked(self, vehicle: dict) -> None:
        confirmation = QMessageBox.question(
            self, "Excluir veículo",
            f"Tem certeza que deseja excluir o veículo {vehicle['plate']}?\n\nEsta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        worker = ApiWorker(self._api_client.delete_vehicle, self._session.access_token, vehicle["id"])
        worker.succeeded.connect(lambda _r: self._handle_delete_succeeded(vehicle["plate"]))
        worker.failed.connect(self._handle_load_failed)
        worker.start()
        self._delete_worker = worker

    def _handle_delete_succeeded(self, plate: str) -> None:
        self._show_status(f"Veículo {plate} excluído.")
        self._load_vehicles()

    def _show_status(self, message: str, *, is_error: bool = False) -> None:
        self._status_message.setObjectName("ErrorBanner" if is_error else "Muted")
        self._status_message.style().unpolish(self._status_message)
        self._status_message.style().polish(self._status_message)
        self._status_message.setText(message)
        self._status_message.show()
        if not is_error:
            QTimer.singleShot(4000, self._status_message.hide)
