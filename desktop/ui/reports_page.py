"""Reports screen (seção 17): gera uma prévia na tela e exporta em Excel,
CSV ou PDF — as colunas e o título vêm do backend, então esta tela nunca
precisa saber o formato de cada tipo de relatório, só exibir o que recebe.
"""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
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
from ui.theme import apply_shadow

_REPORT_TYPES = [
    ("Operações", "operacoes"), ("Ocorrências", "ocorrencias"),
    ("Veículos", "veiculos"), ("Ranking de transportadoras", "transportadoras"),
]
_FORMATS = [("Excel (.xlsx)", "xlsx", "xlsx"), ("CSV", "csv", "csv"), ("PDF", "pdf", "pdf")]
_FORMAT_FILTERS = {"xlsx": "Excel (*.xlsx)", "csv": "CSV (*.csv)", "pdf": "PDF (*.pdf)"}


class ReportsPage(QWidget):
    def __init__(self, api_client: ApiClient, session: UserSession) -> None:
        super().__init__()
        self._api_client = api_client
        self._session = session
        self._carriers: list[dict] = []
        self._preview_worker: ApiWorker | None = None
        self._export_worker: ApiWorker | None = None
        self._has_preview = False

        self._build_ui()
        self._load_carriers()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(QLabel("Relatórios", objectName="PageTitle"))
        header.addStretch(1)
        layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        toolbar.addWidget(QLabel("Tipo:", objectName="Muted"))
        self._type_combo = QComboBox()
        for label, _value in _REPORT_TYPES:
            self._type_combo.addItem(label)
        toolbar.addWidget(self._type_combo)

        toolbar.addWidget(QLabel("Transportadora:", objectName="Muted"))
        self._carrier_combo = QComboBox()
        self._carrier_combo.addItem("Todas", None)
        toolbar.addWidget(self._carrier_combo)

        toolbar.addWidget(QLabel("Período:", objectName="Muted"))
        self._period_start = QDateEdit()
        self._period_start.setCalendarPopup(True)
        self._period_start.setDisplayFormat("dd/MM/yyyy")
        self._period_start.setDate(QDate.currentDate().addDays(-29))
        toolbar.addWidget(self._period_start)
        toolbar.addWidget(QLabel("—", objectName="Muted"))
        self._period_end = QDateEdit()
        self._period_end.setCalendarPopup(True)
        self._period_end.setDisplayFormat("dd/MM/yyyy")
        self._period_end.setDate(QDate.currentDate())
        toolbar.addWidget(self._period_end)
        layout.addLayout(toolbar)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        generate_button = QPushButton("Gerar prévia", objectName="SecondaryButton")
        generate_button.clicked.connect(self._handle_generate_clicked)
        action_row.addWidget(generate_button)

        action_row.addWidget(QLabel("Formato:", objectName="Muted"))
        self._format_combo = QComboBox()
        for label, _value, _ext in _FORMATS:
            self._format_combo.addItem(label)
        action_row.addWidget(self._format_combo)

        self._export_button = QPushButton("⬇ Exportar arquivo", objectName="PrimaryButton")
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(self._handle_export_clicked)
        action_row.addWidget(self._export_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self._status_message = QLabel("Escolha um tipo de relatório e clique em \"Gerar prévia\".")
        self._status_message.setObjectName("Muted")
        layout.addWidget(self._status_message)

        self._table = QTableWidget(0, 0)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(38)
        apply_shadow(self._table, blur=20, y_offset=4, alpha=15)
        layout.addWidget(self._table, stretch=1)

    def _load_carriers(self) -> None:
        worker = ApiWorker(self._api_client.list_carriers, self._session.access_token, page_size=100)
        worker.succeeded.connect(self._handle_carriers_loaded)
        worker.failed.connect(lambda _exc: None)
        worker.start()
        self._carrier_worker = worker

    def _handle_carriers_loaded(self, result: dict) -> None:
        self._carriers = result.get("items", [])
        for carrier in self._carriers:
            self._carrier_combo.addItem(carrier["legal_name"], carrier["id"])

    # --- filtros / prévia ---

    def _current_filters(self) -> dict:
        return {
            "period_start": self._period_start.date().toString("yyyy-MM-dd"),
            "period_end": self._period_end.date().toString("yyyy-MM-dd"),
            "carrier_id": self._carrier_combo.currentData(),
        }

    def _current_report_type(self) -> str:
        return _REPORT_TYPES[self._type_combo.currentIndex()][1]

    def _current_format(self) -> tuple[str, str]:
        _label, export_format, ext = _FORMATS[self._format_combo.currentIndex()]
        return export_format, ext

    def _handle_generate_clicked(self) -> None:
        self._status_message.setText("Gerando prévia...")
        self._export_button.setEnabled(False)
        self._preview_worker = ApiWorker(
            self._api_client.preview_report, self._session.access_token, self._current_report_type(),
            **self._current_filters(),
        )
        self._preview_worker.succeeded.connect(self._handle_preview_loaded)
        self._preview_worker.failed.connect(self._handle_preview_failed)
        self._preview_worker.start()

    def _handle_preview_loaded(self, result: dict) -> None:
        columns = result["columns"]
        rows = result["rows"]

        self._table.clear()
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self._table.setItem(r, c, QTableWidgetItem(str(value)))
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self._status_message.setObjectName("Muted")
        self._status_message.setText(f"{result['subtitle']} — {result['row_count']} registro(s) encontrado(s).")
        self._repolish_status()
        self._has_preview = True
        self._export_button.setEnabled(True)

    def _handle_preview_failed(self, exc: Exception) -> None:
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível gerar a prévia."
        self._status_message.setObjectName("ErrorBanner")
        self._status_message.setText(message)
        self._repolish_status()
        self._has_preview = False
        self._export_button.setEnabled(False)

    def _repolish_status(self) -> None:
        self._status_message.style().unpolish(self._status_message)
        self._status_message.style().polish(self._status_message)

    # --- exportação ---

    def _handle_export_clicked(self) -> None:
        report_type = self._current_report_type()
        export_format, ext = self._current_format()
        default_name = f"opsflow_{report_type}.{ext}"
        path, _filter = QFileDialog.getSaveFileName(
            self, "Salvar relatório", default_name, _FORMAT_FILTERS[export_format],
        )
        if not path:
            return

        self._export_button.setEnabled(False)
        self._export_worker = ApiWorker(
            self._api_client.export_report, self._session.access_token, report_type, export_format,
            **self._current_filters(),
        )
        self._export_worker.succeeded.connect(lambda content: self._save_file(path, content))
        self._export_worker.failed.connect(self._handle_export_failed)
        self._export_worker.start()

    def _save_file(self, path: str, content: bytes) -> None:
        self._export_button.setEnabled(True)
        try:
            with open(path, "wb") as file:
                file.write(content)
        except OSError as exc:
            self._status_message.setObjectName("ErrorBanner")
            self._status_message.setText(f"Não foi possível salvar o arquivo: {exc}")
            self._repolish_status()
            return
        self._status_message.setObjectName("Muted")
        self._status_message.setText(f"Relatório salvo em {path}")
        self._repolish_status()

    def _handle_export_failed(self, exc: Exception) -> None:
        self._export_button.setEnabled(self._has_preview)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível exportar o relatório."
        self._status_message.setObjectName("ErrorBanner")
        self._status_message.setText(message)
        self._repolish_status()
