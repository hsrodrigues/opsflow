"""Main application shell (seção 26): sidebar + topbar + content + status bar.

The content area is a `QStackedWidget`; each enabled nav item owns a page
(built lazily, on first visit, so we don't fire API calls for screens the
user never opens). Items still pending their fase stay visible — so the
product's real shape shows — but disabled with a "em breve" tooltip rather
than opening a screen that fakes doing something.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import DesktopConfig
from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker
from ui.carriers_page import CarriersPage
from ui.dashboard_page import DashboardPage
from ui.drivers_page import DriversPage
from ui.license_page import LicensePage
from ui.notification_panel import NotificationBell
from ui.occurrences_page import OccurrencesPage
from ui.operations_page import OperationsPage
from ui.products_page import ProductsPage
from ui.reports_page import ReportsPage
from ui.routes_page import RoutesPage
from ui.schedules_page import SchedulesPage
from ui.settings_page import SettingsPage
from ui.users_page import UsersPage
from ui.vehicles_page import VehiclesPage
from ui.widgets import build_logo_mark

# Navegação agrupada por seção (padrão comum em ERPs: Visão Geral / Cadastros
# / Operação / Sistema), cada item como (rótulo, habilitado, fábrica da
# página — None para itens ainda sem tela).
_NAV_SECTIONS = [
    ("VISÃO GERAL", [
        ("Dashboard", True, lambda self: DashboardPage(self._api_client, self._session)),
    ]),
    ("CADASTROS", [
        ("Veículos", True, lambda self: VehiclesPage(self._api_client, self._session)),
        ("Motoristas", True, lambda self: DriversPage(self._api_client, self._session)),
        ("Transportadoras", True, lambda self: CarriersPage(self._api_client, self._session)),
        ("Rotas", True, lambda self: RoutesPage(self._api_client, self._session)),
        ("Produtos", True, lambda self: ProductsPage(self._api_client, self._session)),
    ]),
    ("OPERAÇÃO", [
        ("Programação", True, lambda self: SchedulesPage(self._api_client, self._session)),
        ("Centro de Operações", True, lambda self: OperationsPage(self._api_client, self._session)),
        ("Ocorrências", True, lambda self: OccurrencesPage(self._api_client, self._session)),
    ]),
    ("ANÁLISE", [
        ("Relatórios", True, lambda self: ReportsPage(self._api_client, self._session)),
    ]),
    ("SISTEMA", [
        ("Usuários", True, lambda self: UsersPage(self._api_client, self._session)),
        ("Licença", True, lambda self: LicensePage(self._api_client, self._session)),
        ("Configurações", True, lambda self: SettingsPage(self._config, self._api_client, self._session)),
    ]),
]

_HEALTH_POLL_INTERVAL_MS = 15_000


def _initials(name: str) -> str:
    parts = [p for p in name.replace("@", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _repolish(widget: QWidget) -> None:
    """Force Qt to re-evaluate `#ObjectName`-based QSS rules after changing
    `objectName()` at runtime — Qt only applies those rules once, on the
    widget's first polish, so a later `setObjectName()` is otherwise silently
    ignored and the widget keeps its old (or no) styling.
    """
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class MainWindow(QWidget):
    def __init__(
        self, config: DesktopConfig, api_client: ApiClient, session: UserSession, on_logout,
        apply_theme_callback,
    ) -> None:
        super().__init__()
        self._config = config
        self._api_client = api_client
        self._session = session
        self._on_logout = on_logout
        self._apply_theme_callback = apply_theme_callback
        self._dark_mode = False
        self._logout_worker: ApiWorker | None = None
        self._health_worker: ApiWorker | None = None
        self._nav_buttons: list[QPushButton] = []
        self._page_indexes: dict[str, int] = {}

        self.setObjectName("AppRoot")
        self.setWindowTitle("OpsFlow")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 640)

        self._build_ui()
        self._navigate_to("Dashboard")

        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._poll_health)
        self._health_timer.start(_HEALTH_POLL_INTERVAL_MS)
        self._poll_health()

        # Mesma cadência do indicador de conexão — os robôs em background
        # (seção 41) podem gerar uma notificação a qualquer momento, então o
        # contador de não lidas precisa se atualizar sozinho, sem o usuário
        # precisar abrir o sino para descobrir que há algo novo.
        self._notification_timer = QTimer(self)
        self._notification_timer.timeout.connect(self._notification_bell.refresh_count)
        self._notification_timer.start(_HEALTH_POLL_INTERVAL_MS)
        self._notification_bell.refresh_count()

    # --- construção da UI ---

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        right = QVBoxLayout()
        right.setSpacing(0)
        right.addWidget(self._build_topbar())

        self._stack = QStackedWidget()
        right.addWidget(self._stack, stretch=1)

        right.addWidget(self._build_status_bar())

        right_container = QWidget()
        right_container.setLayout(right)
        root.addWidget(right_container, stretch=1)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget(objectName="Sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(build_logo_mark(30))
        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        brand_col.addWidget(QLabel("OPSFLOW", objectName="SidebarBrand"))
        brand_col.addWidget(QLabel("Gestão Operacional", objectName="SidebarTagline"))
        header.addLayout(brand_col)
        header.addStretch(1)
        layout.addLayout(header)
        layout.addSpacing(18)

        for section_index, (section_label, items) in enumerate(_NAV_SECTIONS):
            if section_index > 0:
                layout.addWidget(QLabel(section_label, objectName="SidebarSection"))
            for label, enabled, _factory in items:
                button = QPushButton(label, objectName="NavItem")
                button.setCheckable(True)
                button.setEnabled(enabled)
                if enabled:
                    button.clicked.connect(lambda _checked, name=label: self._navigate_to(name))
                else:
                    button.setToolTip("Disponível em uma próxima fase")
                layout.addWidget(button)
                self._nav_buttons.append(button)

        layout.addStretch(1)
        return sidebar

    def _build_topbar(self) -> QWidget:
        topbar = QWidget(objectName="Topbar")
        topbar.setFixedHeight(60)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(24, 0, 20, 0)

        self._page_title = QLabel("Dashboard", objectName="PageTitle")
        layout.addWidget(self._page_title)
        layout.addStretch(1)

        self._connection_label = QLabel("🟢 Conectado")
        self._connection_label.setObjectName("StatusOnline")
        layout.addWidget(self._connection_label)
        layout.addSpacing(16)

        self._notification_bell = NotificationBell(self._api_client, self._session)
        layout.addWidget(self._notification_bell)
        layout.addSpacing(10)

        theme_button = QPushButton("🌙", objectName="IconButton")
        theme_button.setToolTip("Alternar tema claro/escuro")
        theme_button.setFixedSize(32, 32)
        theme_button.clicked.connect(self._toggle_theme)
        layout.addWidget(theme_button)
        layout.addSpacing(18)

        avatar = QLabel(_initials(self._session.full_name or self._session.email or "?"), objectName="Avatar")
        avatar.setFixedSize(30, 30)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(avatar)
        layout.addSpacing(8)

        user_label = QLabel(self._session.full_name or self._session.email or "")
        layout.addWidget(user_label)
        layout.addSpacing(12)

        logout_button = QPushButton("Sair", objectName="LinkButton")
        logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_button.clicked.connect(self._handle_logout_clicked)
        layout.addWidget(logout_button)

        return topbar

    def _build_status_bar(self) -> QWidget:
        bar = QWidget(objectName="StatusBar")
        bar.setFixedHeight(30)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.addWidget(QLabel(f"OpsFlow {self._config.app_version}", objectName="Muted"))
        layout.addStretch(1)
        tenant_label = QLabel(
            self._session.tenant_name or (f"Empresa #{self._session.tenant_id}" if self._session.tenant_id else "Plataforma")
        )
        tenant_label.setObjectName("Muted")
        layout.addWidget(tenant_label)
        return bar

    # --- navegação ---

    def _navigate_to(self, label: str) -> None:
        if label not in self._page_indexes:
            all_items = [item for _section, items in _NAV_SECTIONS for item in items]
            factory = next(f for lbl, _enabled, f in all_items if lbl == label)
            page = factory(self)
            self._page_indexes[label] = self._stack.addWidget(page)

        self._stack.setCurrentIndex(self._page_indexes[label])
        self._page_title.setText(label)
        for button in self._nav_buttons:
            button.setChecked(button.text() == label)

    # --- ações ---

    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        self._apply_theme_callback(dark=self._dark_mode)
        # QSS não estiliza QtCharts nem o viewport de um QScrollArea dentro
        # de uma janela translúcida (ver `notification_panel.py`) — quem
        # precisa repintar na cor certa expõe um `apply_theme(dark=...)`,
        # chamado aqui se existir.
        self._notification_bell.apply_theme(dark=self._dark_mode)
        for index in self._page_indexes.values():
            page = self._stack.widget(index)
            if hasattr(page, "apply_theme"):
                page.apply_theme(dark=self._dark_mode)

    def _handle_logout_clicked(self) -> None:
        if not self._session.refresh_token:
            self._on_logout()
            return
        self._logout_worker = ApiWorker(self._api_client.logout, self._session.refresh_token)
        self._logout_worker.succeeded.connect(lambda _result: self._on_logout())
        self._logout_worker.failed.connect(lambda _exc: self._on_logout())
        self._logout_worker.start()

    def _poll_health(self) -> None:
        self._health_worker = ApiWorker(self._api_client.check_health)
        self._health_worker.succeeded.connect(self._handle_health_result)
        self._health_worker.failed.connect(lambda _exc: self._set_connection_status(False))
        self._health_worker.start()

    def _handle_health_result(self, result: dict) -> None:
        self._set_connection_status(result.get("status") in ("ok", "degraded"))

    def _set_connection_status(self, online: bool) -> None:
        if online:
            self._connection_label.setText("🟢 Conectado")
            self._connection_label.setObjectName("StatusOnline")
        else:
            self._connection_label.setText("🔴 Offline")
            self._connection_label.setObjectName("StatusOffline")
        _repolish(self._connection_label)
