"""Schedules screen — Programação Operacional (seção 13)."""
from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
from ui.duplicate_schedule_dialog import DuplicateScheduleDialog
from ui.schedule_dialog import ScheduleItemDialog
from ui.status_change_dialog import StatusChangeDialog
from ui.theme import apply_shadow
from ui.widgets import build_badge
from utils.formatting import format_datetime_br

_STATUS_FILTER_OPTIONS = [
    ("Todos os status", None), ("Programado", "PROGRAMADO"), ("Aguardando", "AGUARDANDO"),
    ("Em fila", "EM_FILA"), ("Em operação", "EM_OPERACAO"), ("Concluído", "CONCLUIDO"),
    ("Atrasado", "ATRASADO"), ("Cancelado", "CANCELADO"),
]
_STATUS_DISPLAY = {
    "PROGRAMADO": ("Programado", "BadgeNeutral"), "AGUARDANDO": ("Aguardando", "BadgeInfo"),
    "EM_FILA": ("Em fila", "BadgeInfo"), "EM_OPERACAO": ("Em operação", "BadgeInfo"),
    "CONCLUIDO": ("Concluído", "BadgeSuccess"), "ATRASADO": ("Atrasado", "BadgeDanger"),
    "CANCELADO": ("Cancelado", "BadgeNeutral"),
}
_PAGE_SIZE = 20


class SchedulesPage(QWidget):
    def __init__(self, api_client: ApiClient, session: UserSession) -> None:
        super().__init__()
        self._api_client = api_client
        self._session = session
        self._page = 1
        self._total_pages = 1
        self._routes: list[dict] = []
        self._carriers: list[dict] = []
        self._vehicles: list[dict] = []
        self._drivers: list[dict] = []
        self._products: list[dict] = []
        self._worker: ApiWorker | None = None

        self._build_ui()
        self._load_reference_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(QLabel("Programação", objectName="PageTitle"))
        header.addStretch(1)
        self._duplicate_button = QPushButton("Duplicar programação", objectName="SecondaryButton")
        self._duplicate_button.clicked.connect(self._handle_duplicate_clicked)
        header.addWidget(self._duplicate_button)
        self._new_button = QPushButton("+ Nova Programação", objectName="PrimaryButton")
        self._new_button.setEnabled(False)
        self._new_button.clicked.connect(self._handle_new_clicked)
        header.addWidget(self._new_button)
        layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Data:", objectName="Muted"))
        self._date_filter = QDateEdit()
        self._date_filter.setCalendarPopup(True)
        self._date_filter.setDisplayFormat("dd/MM/yyyy")
        self._date_filter.setDate(QDate.currentDate())
        self._date_filter.dateChanged.connect(self._handle_search)
        toolbar.addWidget(self._date_filter)
        toolbar.addSpacing(12)

        self._status_filter = QComboBox()
        for label, _value in _STATUS_FILTER_OPTIONS:
            self._status_filter.addItem(label)
        self._status_filter.currentIndexChanged.connect(self._handle_search)
        toolbar.addWidget(self._status_filter)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self._status_message = QLabel("")
        self._status_message.setObjectName("Muted")
        self._status_message.hide()
        layout.addWidget(self._status_message)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["Rota", "Veículo", "Motorista", "Horário previsto", "Status", ""])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 110)
        self._table.setColumnWidth(3, 150)
        self._table.setColumnWidth(4, 120)
        self._table.setColumnWidth(5, 170)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(44)
        apply_shadow(self._table, blur=20, y_offset=4, alpha=15)
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

    # --- carregamento de dados de referência (rota/transportadora/veículo/motorista) ---

    def _load_reference_data(self) -> None:
        self._worker = ApiWorker(self._api_client.list_routes, self._session.access_token, page_size=100, status="ATIVA")
        self._worker.succeeded.connect(self._handle_routes_loaded)
        self._worker.failed.connect(lambda _exc: self._load_items())
        self._worker.start()

    def _handle_routes_loaded(self, result: dict) -> None:
        self._routes = result.get("items", [])
        self._worker = ApiWorker(self._api_client.list_carriers, self._session.access_token, page_size=100)
        self._worker.succeeded.connect(self._handle_carriers_loaded)
        self._worker.failed.connect(lambda _exc: self._load_items())
        self._worker.start()

    def _handle_carriers_loaded(self, result: dict) -> None:
        self._carriers = result.get("items", [])
        self._worker = ApiWorker(self._api_client.list_vehicles, self._session.access_token, page_size=100)
        self._worker.succeeded.connect(self._handle_vehicles_loaded)
        self._worker.failed.connect(lambda _exc: self._load_items())
        self._worker.start()

    def _handle_vehicles_loaded(self, result: dict) -> None:
        self._vehicles = result.get("items", [])
        self._worker = ApiWorker(self._api_client.list_drivers, self._session.access_token, page_size=100)
        self._worker.succeeded.connect(self._handle_drivers_loaded)
        self._worker.failed.connect(lambda _exc: self._load_items())
        self._worker.start()

    def _handle_drivers_loaded(self, result: dict) -> None:
        self._drivers = result.get("items", [])
        self._worker = ApiWorker(self._api_client.list_products, self._session.access_token, page_size=100)
        self._worker.succeeded.connect(self._handle_products_loaded)
        self._worker.failed.connect(lambda _exc: self._load_items())
        self._worker.start()

    def _handle_products_loaded(self, result: dict) -> None:
        self._products = result.get("items", [])
        self._new_button.setEnabled(bool(self._routes))
        if not self._routes:
            self._show_status("Cadastre ao menos uma rota antes de criar programações.", is_error=True)
        self._load_items()

    # --- listagem de programações ---

    def _handle_search(self) -> None:
        self._page = 1
        self._load_items()

    def _go_previous_page(self) -> None:
        if self._page > 1:
            self._page -= 1
            self._load_items()

    def _go_next_page(self) -> None:
        if self._page < self._total_pages:
            self._page += 1
            self._load_items()

    def _load_items(self) -> None:
        status_value = _STATUS_FILTER_OPTIONS[self._status_filter.currentIndex()][1]
        self._worker = ApiWorker(
            self._api_client.list_schedule_items, self._session.access_token,
            schedule_date=self._date_filter.date().toString("yyyy-MM-dd"), status=status_value,
            page=self._page, page_size=_PAGE_SIZE,
        )
        self._worker.succeeded.connect(self._handle_items_loaded)
        self._worker.failed.connect(self._handle_load_failed)
        self._worker.start()

    def _handle_items_loaded(self, result: dict) -> None:
        items = result["items"]
        meta = result["meta"]
        self._total_pages = meta["total_pages"]
        self._page = meta["page"]

        self._table.setRowCount(0)
        for row, item in enumerate(items):
            self._table.insertRow(row)
            route_item = QTableWidgetItem(item["route_name"])
            route_font = route_item.font()
            route_font.setBold(True)
            route_item.setFont(route_font)
            self._table.setItem(row, 0, route_item)
            self._table.setItem(row, 1, QTableWidgetItem(item.get("vehicle_plate") or "—"))
            self._table.setItem(row, 2, QTableWidgetItem(item.get("driver_name") or "—"))
            scheduled_display = format_datetime_br(item["scheduled_at"])
            self._table.setItem(row, 3, QTableWidgetItem(scheduled_display))
            text, badge_class = _STATUS_DISPLAY.get(item["status"], (item["status"], "BadgeNeutral"))
            self._table.setCellWidget(row, 4, build_badge(text, badge_class))
            self._table.setCellWidget(row, 5, self._build_row_actions(item))

        self._page_label.setText(f"Página {meta['page']} de {meta['total_pages']} — {meta['total']} programação(ões)")
        self._prev_button.setEnabled(self._page > 1)
        self._next_button.setEnabled(self._page < self._total_pages)

    def _handle_load_failed(self, exc: Exception) -> None:
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível carregar a programação."
        self._show_status(message, is_error=True)

    def _build_row_actions(self, item: dict) -> QWidget:
        container = QWidget()
        row_layout = QHBoxLayout(container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        status_button = QPushButton("Status", objectName="LinkButton")
        status_button.setCursor(Qt.CursorShape.PointingHandCursor)
        status_button.clicked.connect(lambda: self._handle_status_clicked(item))
        edit_button = QPushButton("Editar", objectName="LinkButton")
        edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_button.clicked.connect(lambda: self._handle_edit_clicked(item))
        row_layout.addWidget(status_button)
        row_layout.addWidget(edit_button)
        # Só dá pra excluir enquanto ainda não virou uma operação de verdade
        # (seção 21) — depois disso ela carrega histórico operacional e o
        # caminho é cancelar via Status, não apagar (mesmo backend que já
        # recusa a exclusão nesse caso, ver `schedule_service.py`).
        if item["status"] == "PROGRAMADO":
            delete_button = QPushButton("Excluir", objectName="DangerLinkButton")
            delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_button.clicked.connect(lambda: self._handle_delete_clicked(item))
            row_layout.addWidget(delete_button)
        row_layout.addStretch(1)
        return container

    # --- ações ---

    def _handle_new_clicked(self) -> None:
        dialog = ScheduleItemDialog(
            self._api_client, self._session.access_token, self._routes, self._carriers, self._vehicles,
            self._drivers, self._products,
        )
        if dialog.exec():
            self._show_status("Programação criada com sucesso.")
            self._load_items()

    def _handle_duplicate_clicked(self) -> None:
        dialog = DuplicateScheduleDialog(
            self._api_client, self._session.access_token, source_date=self._date_filter.date(),
        )
        if dialog.exec():
            self._show_status(f"{dialog.items_created} item(ns) duplicado(s) com sucesso.")
            self._load_items()

    def _handle_edit_clicked(self, item: dict) -> None:
        dialog = ScheduleItemDialog(
            self._api_client, self._session.access_token, self._routes, self._carriers, self._vehicles,
            self._drivers, self._products, item=item,
        )
        if dialog.exec():
            self._show_status("Programação atualizada com sucesso.")
            self._load_items()

    def _handle_status_clicked(self, item: dict) -> None:
        dialog = StatusChangeDialog(self._api_client, self._session.access_token, item)
        if dialog.exec():
            self._show_status("Status atualizado com sucesso.")
            self._load_items()

    def _handle_delete_clicked(self, item: dict) -> None:
        confirmation = QMessageBox.question(
            self, "Excluir programação",
            f"Tem certeza que deseja excluir a programação da rota {item['route_name']}?\n\n"
            "Esta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        worker = ApiWorker(self._api_client.delete_schedule_item, self._session.access_token, item["id"])
        worker.succeeded.connect(lambda _r: self._handle_delete_succeeded())
        worker.failed.connect(self._handle_load_failed)
        worker.start()
        self._delete_worker = worker

    def _handle_delete_succeeded(self) -> None:
        self._show_status("Programação excluída.")
        self._load_items()

    def _show_status(self, message: str, *, is_error: bool = False) -> None:
        self._status_message.setObjectName("ErrorBanner" if is_error else "Muted")
        self._status_message.style().unpolish(self._status_message)
        self._status_message.style().polish(self._status_message)
        self._status_message.setText(message)
        self._status_message.show()
        if not is_error:
            QTimer.singleShot(4000, self._status_message.hide)
