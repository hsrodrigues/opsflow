"""Main application shell (seção 26): sidebar + topbar + content + status bar.

Only "Dashboard" is wired to real content in this vertical slice — the
other nav items exist (so the product's real shape is visible) but are
disabled with a "em breve" tooltip until their fase lands, rather than
faking a screen that does nothing.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import DesktopConfig
from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker

_NAV_ITEMS = [
    ("Dashboard", True),
    ("Veículos", False),
    ("Motoristas", False),
    ("Transportadoras", False),
    ("Rotas", False),
    ("Programação", False),
    ("Centro de Operações", False),
    ("Ocorrências", False),
    ("Relatórios", False),
    ("Configurações", False),
]

_HEALTH_POLL_INTERVAL_MS = 15_000


def _repolish(widget: QWidget) -> None:
    """Force Qt to re-evaluate `#ObjectName`-based QSS rules after changing
    `objectName()` at runtime — Qt only applies those rules once, on the
    widget's first polish, so a later `setObjectName()` is otherwise silently
    ignored and the widget keeps its old (or no) styling.
    """
    widget.style().unpolish(widget)
    widget.style().polish(widget)

_ROLE_LABELS = {
    "SUPER_ADMIN": "Administrador da Plataforma",
    "ADMIN_EMPRESA": "Administrador",
    "SUPERVISOR": "Supervisor",
    "OPERADOR": "Operador",
    "VISUALIZADOR": "Visualizador",
}

_LICENSE_LABELS = {
    "ACTIVE": ("Licença ativa", None),
    "TRIAL": ("Você está em período de teste.", "LicenseBannerTrial"),
    "SUSPENDED": ("Licença suspensa — contate o suporte para reativar.", "LicenseBannerExpired"),
    "EXPIRED": ("Licença expirada — contate o suporte para renovar.", "LicenseBannerExpired"),
    "CANCELLED": ("Licença cancelada — contate o suporte.", "LicenseBannerExpired"),
}


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

        self.setObjectName("AppRoot")
        self.setWindowTitle("OpsFlow")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 640)

        self._build_ui()
        self._populate_welcome_card()

        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._poll_health)
        self._health_timer.start(_HEALTH_POLL_INTERVAL_MS)
        self._poll_health()

    # --- construção da UI ---

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        right = QVBoxLayout()
        right.setSpacing(0)
        right.addWidget(self._build_topbar())
        right.addWidget(self._build_content(), stretch=1)
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

        layout.addWidget(QLabel("OPSFLOW", objectName="SidebarBrand"))
        layout.addWidget(QLabel("Gestão Operacional", objectName="SidebarTagline"))
        layout.addSpacing(24)

        for label, enabled in _NAV_ITEMS:
            button = QPushButton(label, objectName="NavItem")
            button.setCheckable(True)
            button.setChecked(enabled and label == "Dashboard")
            button.setEnabled(enabled)
            if not enabled:
                button.setToolTip("Disponível em uma próxima fase")
            layout.addWidget(button)

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

        theme_button = QPushButton("🌙", objectName="IconButton")
        theme_button.setToolTip("Alternar tema claro/escuro")
        theme_button.setFixedSize(32, 32)
        theme_button.clicked.connect(self._toggle_theme)
        layout.addWidget(theme_button)
        layout.addSpacing(16)

        user_label = QLabel(self._session.full_name or self._session.email or "")
        layout.addWidget(user_label)
        layout.addSpacing(8)

        logout_button = QPushButton("Sair", objectName="LinkButton")
        logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_button.clicked.connect(self._handle_logout_clicked)
        layout.addWidget(logout_button)

        return topbar

    def _build_content(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        self._license_banner = QLabel("")
        self._license_banner.hide()
        layout.addWidget(self._license_banner)

        welcome = QLabel("")
        welcome.setObjectName("PageTitle")
        self._welcome_label = welcome
        layout.addWidget(welcome)

        subtitle = QLabel("")
        subtitle.setObjectName("Muted")
        self._subtitle_label = subtitle
        layout.addWidget(subtitle)
        layout.addSpacing(8)

        cards_grid = QGridLayout()
        cards_grid.setSpacing(16)
        self._cards_grid = cards_grid
        layout.addLayout(cards_grid)

        layout.addStretch(1)
        return content

    def _build_status_bar(self) -> QWidget:
        bar = QWidget(objectName="StatusBar")
        bar.setFixedHeight(30)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.addWidget(QLabel(f"OpsFlow {self._config.app_version}", objectName="Muted"))
        layout.addStretch(1)
        tenant_label = QLabel(f"Empresa #{self._session.tenant_id}" if self._session.tenant_id else "Plataforma")
        tenant_label.setObjectName("Muted")
        layout.addWidget(tenant_label)
        return bar

    # --- dados ---

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

        cards = [
            ("Plano", self._session.license_plan_code or "—"),
            ("Status da licença", self._session.license_status or "—"),
            ("Permissões concedidas", str(len(self._session.permissions))),
            ("Papéis", str(len(self._session.roles))),
        ]
        for index, (label, value) in enumerate(cards):
            self._cards_grid.addWidget(self._build_stat_card(label, value), 0, index)

    @staticmethod
    def _build_stat_card(label: str, value: str) -> QFrame:
        card = QFrame(objectName="Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        value_label = QLabel(value, objectName="CardValue")
        layout.addWidget(value_label)
        layout.addWidget(QLabel(label, objectName="CardLabel"))
        return card

    # --- ações ---

    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        self._apply_theme_callback(dark=self._dark_mode)

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
