"""Occurrences screen (seção 14): pesquisa por severidade/status, criar/editar."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
from ui.occurrence_dialog import OccurrenceDialog
from ui.theme import apply_shadow
from ui.widgets import build_badge

_SEVERITY_FILTER_OPTIONS = [
    ("Todas as severidades", None), ("Crítica", "CRITICA"), ("Alta", "ALTA"), ("Média", "MEDIA"), ("Baixa", "BAIXA"),
]
_SEVERITY_DISPLAY = {
    "CRITICA": ("Crítica", "BadgeDanger"), "ALTA": ("Alta", "BadgeWarning"),
    "MEDIA": ("Média", "BadgeInfo"), "BAIXA": ("Baixa", "BadgeNeutral"),
}
_STATUS_FILTER_OPTIONS = [
    ("Todos os status", None), ("Aberta", "ABERTA"), ("Em análise", "EM_ANALISE"),
    ("Resolvida", "RESOLVIDA"), ("Cancelada", "CANCELADA"),
]
_STATUS_DISPLAY = {
    "ABERTA": ("Aberta", "BadgeDanger"), "EM_ANALISE": ("Em análise", "BadgeWarning"),
    "RESOLVIDA": ("Resolvida", "BadgeSuccess"), "CANCELADA": ("Cancelada", "BadgeNeutral"),
}
_PAGE_SIZE = 15


class OccurrencesPage(QWidget):
    def __init__(self, api_client: ApiClient, session: UserSession) -> None:
        super().__init__()
        self._api_client = api_client
        self._session = session
        self._page = 1
        self._total_pages = 1
        self._vehicles: list[dict] = []
        self._drivers: list[dict] = []
        self._worker: ApiWorker | None = None

        self._build_ui()
        self._load_reference_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(QLabel("Ocorrências", objectName="PageTitle"))
        header.addStretch(1)
        self._new_button = QPushButton("+ Nova Ocorrência", objectName="PrimaryButton")
        self._new_button.clicked.connect(self._handle_new_clicked)
        header.addWidget(self._new_button)
        layout.addLayout(header)

        toolbar = QHBoxLayout()
        self._severity_filter = QComboBox()
        for label, _value in _SEVERITY_FILTER_OPTIONS:
            self._severity_filter.addItem(label)
        self._severity_filter.currentIndexChanged.connect(self._handle_search)
        toolbar.addWidget(self._severity_filter)

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

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Data/Hora", "Tipo", "Veículo", "Motorista", "Severidade", "Status", ""]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 140)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(4, 100)
        self._table.setColumnWidth(5, 120)
        self._table.setColumnWidth(6, 110)
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

    def _load_reference_data(self) -> None:
        worker = ApiWorker(self._api_client.list_vehicles, self._session.access_token, page_size=100)
        worker.succeeded.connect(self._handle_vehicles_loaded)
        worker.failed.connect(lambda _exc: self._load_occurrences())
        worker.start()
        self._reference_worker = worker

    def _handle_vehicles_loaded(self, result: dict) -> None:
        self._vehicles = result.get("items", [])
        worker = ApiWorker(self._api_client.list_drivers, self._session.access_token, page_size=100)
        worker.succeeded.connect(self._handle_drivers_loaded)
        worker.failed.connect(lambda _exc: self._load_occurrences())
        worker.start()
        self._reference_worker = worker

    def _handle_drivers_loaded(self, result: dict) -> None:
        self._drivers = result.get("items", [])
        self._load_occurrences()

    def _handle_search(self) -> None:
        self._page = 1
        self._load_occurrences()

    def _go_previous_page(self) -> None:
        if self._page > 1:
            self._page -= 1
            self._load_occurrences()

    def _go_next_page(self) -> None:
        if self._page < self._total_pages:
            self._page += 1
            self._load_occurrences()

    def _load_occurrences(self) -> None:
        severity_value = _SEVERITY_FILTER_OPTIONS[self._severity_filter.currentIndex()][1]
        status_value = _STATUS_FILTER_OPTIONS[self._status_filter.currentIndex()][1]
        self._worker = ApiWorker(
            self._api_client.list_occurrences, self._session.access_token,
            severity=severity_value, status=status_value, page=self._page, page_size=_PAGE_SIZE,
        )
        self._worker.succeeded.connect(self._handle_occurrences_loaded)
        self._worker.failed.connect(self._handle_load_failed)
        self._worker.start()

    def _handle_occurrences_loaded(self, result: dict) -> None:
        items = result["items"]
        meta = result["meta"]
        self._total_pages = meta["total_pages"]
        self._page = meta["page"]

        self._table.setRowCount(0)
        for row, occurrence in enumerate(items):
            self._table.insertRow(row)
            when = occurrence["occurred_at"].replace("T", " ")[:16]
            self._table.setItem(row, 0, QTableWidgetItem(when))
            type_item = QTableWidgetItem(occurrence["occurrence_type_name"])
            type_font = type_item.font()
            type_font.setBold(True)
            type_item.setFont(type_font)
            self._table.setItem(row, 1, type_item)
            self._table.setItem(row, 2, QTableWidgetItem(occurrence.get("vehicle_plate") or "—"))
            self._table.setItem(row, 3, QTableWidgetItem(occurrence.get("driver_name") or "—"))
            sev_text, sev_class = _SEVERITY_DISPLAY.get(occurrence["severity"], (occurrence["severity"], "BadgeNeutral"))
            self._table.setCellWidget(row, 4, build_badge(sev_text, sev_class))
            status_text, status_class = _STATUS_DISPLAY.get(occurrence["status"], (occurrence["status"], "BadgeNeutral"))
            self._table.setCellWidget(row, 5, build_badge(status_text, status_class))
            self._table.setCellWidget(row, 6, self._build_row_actions(occurrence))

        self._page_label.setText(f"Página {meta['page']} de {meta['total_pages']} — {meta['total']} ocorrência(s)")
        self._prev_button.setEnabled(self._page > 1)
        self._next_button.setEnabled(self._page < self._total_pages)

    def _handle_load_failed(self, exc: Exception) -> None:
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível carregar as ocorrências."
        self._show_status(message, is_error=True)

    def _build_row_actions(self, occurrence: dict) -> QWidget:
        container = QWidget()
        row_layout = QHBoxLayout(container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        edit_button = QPushButton("Editar", objectName="LinkButton")
        edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_button.clicked.connect(lambda: self._handle_edit_clicked(occurrence))
        row_layout.addWidget(edit_button)
        row_layout.addStretch(1)
        return container

    def _handle_new_clicked(self) -> None:
        dialog = OccurrenceDialog(self._api_client, self._session.access_token, self._vehicles, self._drivers)
        if dialog.exec():
            self._show_status("Ocorrência registrada com sucesso.")
            self._load_occurrences()

    def _handle_edit_clicked(self, occurrence: dict) -> None:
        dialog = OccurrenceDialog(
            self._api_client, self._session.access_token, self._vehicles, self._drivers, occurrence=occurrence,
        )
        if dialog.exec():
            self._show_status("Ocorrência atualizada com sucesso.")
            self._load_occurrences()

    def _show_status(self, message: str, *, is_error: bool = False) -> None:
        self._status_message.setObjectName("ErrorBanner" if is_error else "Muted")
        self._status_message.style().unpolish(self._status_message)
        self._status_message.style().polish(self._status_message)
        self._status_message.setText(message)
        self._status_message.show()
        if not is_error:
            QTimer.singleShot(4000, self._status_message.hide)
