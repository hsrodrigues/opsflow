"""Dashboard screen (seção 15/16): KPIs + gráficos + filtro de período.

The welcome/license banner from Fase 2 stays at the top; everything below
is real data from `/api/v1/dashboard`.
"""
from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QDateEdit, QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.theme import DARK, LIGHT, apply_shadow

_ROLE_LABELS = {
    "SUPER_ADMIN": "Administrador da Plataforma", "ADMIN_EMPRESA": "Administrador",
    "SUPERVISOR": "Supervisor", "OPERADOR": "Operador", "VISUALIZADOR": "Visualizador",
}
_LICENSE_LABELS = {
    "ACTIVE": ("Licença ativa", None),
    "TRIAL": ("Você está em período de teste.", "LicenseBannerTrial"),
    "SUSPENDED": ("Licença suspensa — contate o suporte para reativar.", "LicenseBannerExpired"),
    "EXPIRED": ("Licença expirada — contate o suporte para renovar.", "LicenseBannerExpired"),
    "CANCELLED": ("Licença cancelada — contate o suporte.", "LicenseBannerExpired"),
}
_STATUS_LABELS = {
    "PROGRAMADO": "Programado", "AGUARDANDO": "Aguardando", "EM_FILA": "Em fila", "EM_OPERACAO": "Em operação",
    "CONCLUIDO": "Concluído", "ATRASADO": "Atrasado", "CANCELADO": "Cancelado",
}
_SEVERITY_LABELS = {"BAIXA": "Baixa", "MEDIA": "Média", "ALTA": "Alta", "CRITICA": "Crítica"}


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class DashboardPage(QWidget):
    def __init__(self, api_client: ApiClient, session: UserSession) -> None:
        super().__init__()
        self._api_client = api_client
        self._session = session
        self._dark_mode = False
        self._summary_worker: ApiWorker | None = None
        self._charts_worker: ApiWorker | None = None

        self._build_ui()
        self._populate_welcome_card()
        self._load_data()

    # --- construção da UI ---

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        self._license_banner = QLabel("")
        self._license_banner.hide()
        layout.addWidget(self._license_banner)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        self._welcome_label = QLabel("", objectName="PageTitle")
        title_col.addWidget(self._welcome_label)
        self._subtitle_label = QLabel("", objectName="Muted")
        title_col.addWidget(self._subtitle_label)
        header.addLayout(title_col)
        header.addStretch(1)

        header.addWidget(QLabel("Período:", objectName="Muted"))
        self._period_start = QDateEdit()
        self._period_start.setCalendarPopup(True)
        self._period_start.setDisplayFormat("dd/MM/yyyy")
        self._period_start.setDate(QDate.currentDate().addDays(-6))
        self._period_start.dateChanged.connect(self._load_data)
        header.addWidget(self._period_start)
        header.addWidget(QLabel("—", objectName="Muted"))
        self._period_end = QDateEdit()
        self._period_end.setCalendarPopup(True)
        self._period_end.setDisplayFormat("dd/MM/yyyy")
        self._period_end.setDate(QDate.currentDate())
        self._period_end.dateChanged.connect(self._load_data)
        header.addWidget(self._period_end)
        layout.addLayout(header)

        self._cards_grid = QGridLayout()
        self._cards_grid.setSpacing(14)
        layout.addLayout(self._cards_grid)
        self._card_labels: dict[str, QLabel] = {}
        self._build_kpi_cards()

        charts_row = QHBoxLayout()
        charts_row.setSpacing(16)
        self._status_chart_view = self._build_chart_placeholder()
        self._carrier_chart_view = self._build_chart_placeholder()
        charts_row.addWidget(self._status_chart_view, stretch=1)
        charts_row.addWidget(self._carrier_chart_view, stretch=1)
        layout.addLayout(charts_row, stretch=1)

        self._severity_chart_view = self._build_chart_placeholder()
        layout.addWidget(self._severity_chart_view, stretch=1)

    def _build_kpi_cards(self) -> None:
        cards = [
            ("operacoes_hoje", "Operações hoje"), ("concluidas", "Concluídas"),
            ("em_andamento", "Em andamento"), ("atrasadas", "Atrasadas"), ("canceladas", "Canceladas"),
            ("veiculos_ativos", "Veículos ativos"), ("ocorrencias", "Ocorrências"),
            ("tempo_medio_minutos", "Tempo médio (min)"), ("taxa_conclusao_percentual", "Taxa de conclusão"),
        ]
        for index, (key, label) in enumerate(cards):
            card = QFrame(objectName="Card")
            apply_shadow(card, blur=18, y_offset=4, alpha=18)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            value_label = QLabel("—", objectName="CardValue")
            self._card_labels[key] = value_label
            card_layout.addWidget(value_label)
            card_layout.addWidget(QLabel(label, objectName="CardLabel"))
            self._cards_grid.addWidget(card, index // 5, index % 5)

    def _build_chart_placeholder(self) -> QChartView:
        chart = QChart()
        chart.legend().hide()
        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(240)
        return view

    def _populate_welcome_card(self) -> None:
        self._welcome_label.setText(f"Bem-vindo, {self._session.full_name}")
        role_labels = ", ".join(_ROLE_LABELS.get(r, r) for r in self._session.roles) or "—"
        self._subtitle_label.setText(f"{self._session.email} · {role_labels}")

        if self._session.license_status:
            text, style = _LICENSE_LABELS.get(self._session.license_status, (self._session.license_status, None))
            self._license_banner.setText(f"ℹ {text}")
            self._license_banner.setObjectName(style or "Muted")
            self._license_banner.setVisible(style is not None)
            _repolish(self._license_banner)

    # --- carregamento de dados ---

    def _period_params(self) -> dict:
        return {
            "period_start": self._period_start.date().toString("yyyy-MM-dd"),
            "period_end": self._period_end.date().toString("yyyy-MM-dd"),
        }

    def _load_data(self) -> None:
        params = self._period_params()
        self._summary_worker = ApiWorker(self._api_client.get_dashboard_summary, self._session.access_token, **params)
        self._summary_worker.succeeded.connect(self._apply_summary)
        self._summary_worker.failed.connect(self._handle_load_failed)
        self._summary_worker.start()

        self._charts_worker = ApiWorker(self._api_client.get_dashboard_charts, self._session.access_token, **params)
        self._charts_worker.succeeded.connect(self._apply_charts)
        self._charts_worker.failed.connect(self._handle_load_failed)
        self._charts_worker.start()

    def _apply_summary(self, summary: dict) -> None:
        for key, label in self._card_labels.items():
            value = summary.get(key)
            if value is None:
                label.setText("—")
            elif key == "taxa_conclusao_percentual":
                label.setText(f"{value:.0f}%")
            elif isinstance(value, float):
                label.setText(f"{value:.1f}")
            else:
                label.setText(str(value))

    def _apply_charts(self, charts: dict) -> None:
        palette = DARK if self._dark_mode else LIGHT
        self._render_bar_chart(
            self._status_chart_view, "Operações por status", charts["operacoes_por_status"], _STATUS_LABELS, palette,
        )
        self._render_bar_chart(
            self._carrier_chart_view, "Operações por transportadora", charts["operacoes_por_transportadora"],
            {}, palette,
        )
        self._render_bar_chart(
            self._severity_chart_view, "Ocorrências por severidade", charts["ocorrencias_por_severidade"],
            _SEVERITY_LABELS, palette,
        )

    def _handle_load_failed(self, exc: Exception) -> None:
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível carregar o dashboard."
        self._welcome_label.setText(message)

    def _render_bar_chart(
        self, view: QChartView, title: str, points: list[dict], label_map: dict, palette,
    ) -> None:
        chart = QChart()
        chart.setTitle(title)
        chart.legend().hide()
        chart.setBackgroundVisible(False)
        chart.setTitleBrush(QColor(palette.text))

        bar_set = QBarSet("valor")
        bar_set.setColor(QColor(palette.accent))
        categories = []
        for point in points:
            bar_set.append(point["value"])
            categories.append(label_map.get(point["label"], point["label"]))

        series = QBarSeries()
        series.append(bar_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsColor(QColor(palette.text_muted))
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setLabelsColor(QColor(palette.text_muted))
        max_value = max((point["value"] for point in points), default=0)
        axis_y.setRange(0, max(1, max_value))
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        view.setChart(chart)

    def apply_theme(self, *, dark: bool) -> None:
        """Chamado pelo MainWindow ao alternar o tema — os gráficos precisam ser
        redesenhados com as novas cores (QSS não estiliza QtCharts)."""
        self._dark_mode = dark
        self._load_data()
