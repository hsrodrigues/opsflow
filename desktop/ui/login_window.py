"""Login screen (seção 5) — the exact fields from the spec's mockup, wired
to the real `/api/v1/auth/login` endpoint.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.config import DesktopConfig
from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.theme import apply_shadow


class LoginWindow(QWidget):
    def __init__(self, config: DesktopConfig, api_client: ApiClient, session: UserSession, on_login_success) -> None:
        super().__init__()
        self._config = config
        self._api_client = api_client
        self._session = session
        self._on_login_success = on_login_success
        self._worker: ApiWorker | None = None

        self.setObjectName("AppRoot")
        self.setWindowTitle("OpsFlow — Entrar")
        self.resize(420, 560)
        self.setMinimumSize(380, 520)

        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(1)

        card = QWidget(objectName="LoginCard")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        apply_shadow(card, blur=40, y_offset=14, alpha=35)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 36, 36, 28)
        card_layout.setSpacing(6)

        logo = QLabel("O", objectName="LoginLogoGlyph")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_wrap = QWidget(objectName="LoginLogo")
        logo_wrap.setFixedSize(52, 52)
        logo_layout = QVBoxLayout(logo_wrap)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.addWidget(logo)
        logo_row = QHBoxLayout()
        logo_row.addStretch(1)
        logo_row.addWidget(logo_wrap)
        logo_row.addStretch(1)
        card_layout.addLayout(logo_row)
        card_layout.addSpacing(16)

        brand = QLabel("OPSFLOW")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setStyleSheet("font-size: 22px; font-weight: 700; letter-spacing: 1px;")
        card_layout.addWidget(brand)

        tagline = QLabel("Gestão Operacional Inteligente")
        tagline.setObjectName("Muted")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(tagline)
        card_layout.addSpacing(24)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        card_layout.addWidget(self._error_label)
        card_layout.addSpacing(4)

        card_layout.addWidget(QLabel("E-mail"))
        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText("seuemail@empresa.com")
        card_layout.addWidget(self._email_input)
        card_layout.addSpacing(10)

        card_layout.addWidget(QLabel("Senha"))
        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setPlaceholderText("••••••••")
        card_layout.addWidget(self._password_input)
        card_layout.addSpacing(12)

        self._remember_checkbox = QCheckBox("Lembrar acesso")
        card_layout.addWidget(self._remember_checkbox)
        card_layout.addSpacing(16)

        self._login_button = QPushButton("ENTRAR")
        self._login_button.setObjectName("PrimaryButton")
        self._login_button.setMinimumHeight(38)
        self._login_button.clicked.connect(self._handle_login_clicked)
        card_layout.addWidget(self._login_button)
        card_layout.addSpacing(12)

        forgot_password = QPushButton("Esqueci minha senha")
        forgot_password.setObjectName("LinkButton")
        forgot_password.setCursor(Qt.CursorShape.PointingHandCursor)
        forgot_password.setToolTip("Em breve — fale com o administrador da sua empresa por enquanto.")
        forgot_password.setEnabled(False)
        card_layout.addWidget(forgot_password, alignment=Qt.AlignmentFlag.AlignHCenter)

        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addSpacing(16)

        footer = QLabel(f"Versão {self._config.app_version}")
        footer.setObjectName("Muted")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(footer)
        outer.addStretch(1)

        self._email_input.returnPressed.connect(self._handle_login_clicked)
        self._password_input.returnPressed.connect(self._handle_login_clicked)
        self._email_input.setFocus()

    def _handle_login_clicked(self) -> None:
        email = self._email_input.text().strip()
        password = self._password_input.text()
        if not email or not password:
            self._show_error("Informe e-mail e senha para continuar.")
            return

        self._set_loading(True)
        self._worker = ApiWorker(
            self._api_client.login, email, password, self._remember_checkbox.isChecked()
        )
        self._worker.succeeded.connect(self._handle_login_succeeded)
        self._worker.failed.connect(self._handle_login_failed)
        self._worker.start()

    def _handle_login_succeeded(self, result: dict) -> None:
        self._set_loading(False)
        user = result["user"]
        license_ = result.get("license")

        self._session.access_token = result["access_token"]
        self._session.refresh_token = result["refresh_token"]
        self._session.user_id = user["id"]
        self._session.email = user["email"]
        self._session.full_name = user["full_name"]
        self._session.tenant_id = user["tenant_id"]
        self._session.roles = user["roles"]
        self._session.permissions = user["permissions"]
        if license_:
            self._session.license_status = license_["status"]
            self._session.license_plan_code = license_["plan_code"]
            self._session.license_expires_at = license_["expires_at"]

        self._on_login_success()

    def _handle_login_failed(self, exc: Exception) -> None:
        self._set_loading(False)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Ocorreu um erro inesperado."
        self._show_error(message)

    def _set_loading(self, loading: bool) -> None:
        self._login_button.setEnabled(not loading)
        self._login_button.setText("ENTRANDO..." if loading else "ENTRAR")
        self._email_input.setEnabled(not loading)
        self._password_input.setEnabled(not loading)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override signature
        if event.key() == Qt.Key.Key_Escape:
            return
        super().keyPressEvent(event)
