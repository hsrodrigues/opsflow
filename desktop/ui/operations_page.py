"""Centro de Operações — real-time operations board (seção 21)."""
from datetime import datetime, timezone

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.theme import apply_shadow
from ui.widgets import build_badge, build_kpi_card

_STATUS_DISPLAY = {
    "AGUARDANDO": ("🟡 Aguardando", "BadgeWarning"), "EM_FILA": ("🟡 Em fila", "BadgeWarning"),
    "EM_OPERACAO": ("🟢 Em operação", "BadgeSuccess"), "ATRASADO": ("🔴 Atrasado", "BadgeDanger"),
}
_REFRESH_INTERVAL_MS = 15_000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _elapsed_since(started_at: str | None) -> str:
    if not started_at:
        return "—"
    started = datetime.fromisoformat(started_at)
    delta = _utc_now() - started
    total_minutes = max(0, int(delta.total_seconds() // 60))
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


class OperationsPage(QWidget):
    def __init__(self, api_client: ApiClient, session: UserSession) -> None:
        super().__init__()
        self._api_client = api_client
        self._session = session
        self._summary_worker: ApiWorker | None = None
        self._list_worker: ApiWorker | None = None

        self._build_ui()
        self._refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(_REFRESH_INTERVAL_MS)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.addWidget(QLabel("Centro de Operações", objectName="PageTitle"))
        header.addStretch(1)
        self._updated_label = QLabel("", objectName="Muted")
        header.addWidget(self._updated_label)
        layout.addLayout(header)

        cards = QGridLayout()
        cards.setSpacing(16)
        self._programadas_card, self._programadas_value = build_kpi_card("🗓️", "IconChipInfo", "Programadas")
        self._em_operacao_card, self._em_operacao_value = build_kpi_card("🚚", "IconChipSuccess", "Em operação")
        self._atrasadas_card, self._atrasadas_value = build_kpi_card("⏱️", "IconChipDanger", "Atrasadas")
        cards.addWidget(self._programadas_card, 0, 0)
        cards.addWidget(self._em_operacao_card, 0, 1)
        cards.addWidget(self._atrasadas_card, 0, 2)
        layout.addLayout(cards)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Operação", "Veículo", "Rota", "Status", "Tempo"])
        header_view = self._table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 110)
        self._table.setColumnWidth(1, 110)
        self._table.setColumnWidth(3, 150)
        self._table.setColumnWidth(4, 90)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(44)
        apply_shadow(self._table, blur=20, y_offset=4, alpha=15)
        layout.addWidget(self._table, stretch=1)

    # --- atualização ---

    def _refresh(self) -> None:
        self._summary_worker = ApiWorker(self._api_client.get_operations_summary, self._session.access_token)
        self._summary_worker.succeeded.connect(self._apply_summary)
        self._summary_worker.failed.connect(lambda _exc: None)
        self._summary_worker.start()

        self._list_worker = ApiWorker(self._api_client.list_operations, self._session.access_token)
        self._list_worker.succeeded.connect(self._apply_operations)
        self._list_worker.failed.connect(lambda _exc: None)
        self._list_worker.start()

    def _apply_summary(self, summary: dict) -> None:
        self._programadas_value.setText(str(summary["programadas"]))
        self._em_operacao_value.setText(str(summary["em_operacao"]))
        self._atrasadas_value.setText(str(summary["atrasadas"]))
        self._updated_label.setText(f"Atualizado às {datetime.now().strftime('%H:%M:%S')}")

    def _apply_operations(self, operations: list) -> None:
        self._table.setRowCount(0)
        for row, operation in enumerate(operations):
            self._table.insertRow(row)
            number_item = QTableWidgetItem(operation["operation_number"])
            number_font = number_item.font()
            number_font.setBold(True)
            number_item.setFont(number_font)
            self._table.setItem(row, 0, number_item)
            self._table.setItem(row, 1, QTableWidgetItem(operation.get("vehicle_plate") or "—"))
            self._table.setItem(row, 2, QTableWidgetItem(operation["route_name"]))
            text, badge_class = _STATUS_DISPLAY.get(operation["status"], (operation["status"], "BadgeNeutral"))
            self._table.setCellWidget(row, 3, build_badge(text, badge_class))
            self._table.setItem(row, 4, QTableWidgetItem(_elapsed_since(operation.get("started_at"))))
