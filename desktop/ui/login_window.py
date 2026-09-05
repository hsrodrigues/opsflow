"""Login screen (seção 5), redesenhada em duas colunas no estilo dos apps
fintech de referência (Stripe/Nubank/Revolut): um painel de marca em
gradiente com destaques reais do produto à esquerda, e o formulário — a
mesma lógica de sempre, só o layout mudou — centrado à direita sobre o
fundo do tema. A janela nasce maximizada (ver `desktop/main.py`), então o
layout precisa preencher bem uma tela cheia em vez de um cartão pequeno
flutuando num fundo vazio.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from app.config import DesktopConfig
from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.activation_dialog import ActivationDialog
from ui.theme import apply_shadow
from ui.widgets import build_logo_mark

_FEATURES = [
    ("🗓️", "Programação inteligente", "Turnos, rotas e veículos organizados em um só lugar."),
    ("📡", "Centro de Operações ao vivo", "Acompanhe o status de cada operação em tempo real."),
    ("📊", "Dashboard executivo", "Indicadores e gráficos atualizados automaticamente."),
]


class LoginWindow(QWidget):
    def __init__(
        self, config: DesktopConfig, api_client: ApiClient, session: UserSession, on_login_success,
        apply_theme_callback,
    ) -> None:
        super().__init__()
        self._config = config
        self._api_client = api_client
        self._session = session
        self._on_login_success = on_login_success
        self._apply_theme_callback = apply_theme_callback
        self._dark_mode = False
        self._worker: ApiWorker | None = None

        self.setObjectName("AppRoot")
        self.setWindowTitle("OpsFlow — Entrar")
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_brand_panel(), stretch=6)
        root.addWidget(self._build_form_panel(), stretch=5)

    # --- painel de marca (esquerda) ---

    def _build_brand_panel(self) -> QWidget:
        panel = QWidget(objectName="LoginBrandPanel")
        panel.setMinimumWidth(420)
        stack = QStackedLayout(panel)
        stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        stack.addWidget(self._build_brand_blobs())
        stack.addWidget(self._build_brand_content())
        return panel

    @staticmethod
    def _build_brand_blobs() -> QWidget:
        # Círculos translúcidos decorativos ancorados nos cantos opostos do
        # painel — o clássico "glow" de tela de login fintech. Ficam numa
        # camada própria (via QStackedLayout, ver `_build_brand_panel`) para
        # não interferir no layout do conteúdo por cima.
        layer = QWidget()
        grid = QGridLayout(layer)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        blob_top = QWidget(objectName="LoginBrandBlob")
        blob_top.setFixedSize(300, 300)
        grid.addWidget(blob_top, 0, 1, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        blob_bottom = QWidget(objectName="LoginBrandBlob")
        blob_bottom.setFixedSize(420, 420)
        grid.addWidget(blob_bottom, 1, 0, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)

        return layer

    def _build_brand_content(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(64, 56, 64, 48)
        layout.addStretch(1)

        layout.addWidget(build_logo_mark(48))
        layout.addSpacing(28)

        layout.addWidget(QLabel("GESTÃO OPERACIONAL INTELIGENTE", objectName="LoginBrandKicker"))
        layout.addSpacing(10)

        headline = QLabel("Sua operação,\nsob controle total.")
        headline.setObjectName("LoginHeadline")
        headline.setWordWrap(True)
        layout.addWidget(headline)
        layout.addSpacing(12)

        subheadline = QLabel(
            "O OpsFlow reúne programação, frota e ocorrências num só sistema —\n"
            "chega de planilha e grupo de WhatsApp para controlar a operação."
        )
        subheadline.setObjectName("LoginSubheadline")
        subheadline.setWordWrap(True)
        layout.addWidget(subheadline)
        layout.addSpacing(40)

        for glyph, title, desc in _FEATURES:
            layout.addLayout(self._build_feature_row(glyph, title, desc))
            layout.addSpacing(18)

        layout.addStretch(2)
        return content

    @staticmethod
    def _build_feature_row(glyph: str, title: str, desc: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(14)

        icon = QWidget(objectName="LoginFeatureIcon")
        icon.setFixedSize(38, 38)
        icon_layout = QVBoxLayout(icon)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        glyph_label = QLabel(glyph, objectName="LoginFeatureGlyph")
        glyph_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(glyph_label)
        row.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        text_col.addWidget(QLabel(title, objectName="LoginFeatureTitle"))
        desc_label = QLabel(desc, objectName="LoginFeatureDesc")
        desc_label.setWordWrap(True)
        text_col.addWidget(desc_label)
        row.addLayout(text_col, stretch=1)

        return row

    # --- painel do formulário (direita) ---

    def _build_form_panel(self) -> QWidget:
        panel = QWidget(objectName="LoginFormPanel")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(24, 20, 24, 24)

        top_bar = QHBoxLayout()
        top_bar.addStretch(1)
        self._theme_button = QPushButton("🌙", objectName="IconButton")
        self._theme_button.setToolTip("Alternar tema claro/escuro")
        self._theme_button.setFixedSize(32, 32)
        self._theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_button.clicked.connect(self._handle_toggle_theme)
        top_bar.addWidget(self._theme_button)
        outer.addLayout(top_bar)

        outer.addStretch(1)
        outer.addWidget(self._build_login_card(), alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addSpacing(16)

        footer = QLabel(f"Versão {self._config.app_version}")
        footer.setObjectName("Muted")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(footer)
        outer.addStretch(2)

        return panel

    def _build_login_card(self) -> QWidget:
        card = QWidget(objectName="LoginCard")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        card.setFixedWidth(400)
        apply_shadow(card, blur=60, y_offset=22, alpha=32, color=(67, 56, 202))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 36, 36, 28)
        card_layout.setSpacing(6)

        title = QLabel("Bem-vindo de volta")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 21px; font-weight: 700;")
        card_layout.addWidget(title)

        tagline = QLabel("Entre com as credenciais da sua empresa")
        tagline.setObjectName("Muted")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(tagline)
        card_layout.addSpacing(22)

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
        card_layout.addSpacing(18)

        self._login_button = QPushButton("ENTRAR")
        self._login_button.setObjectName("PrimaryButton")
        self._login_button.setMinimumHeight(44)
        self._login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_button.clicked.connect(self._handle_login_clicked)
        card_layout.addWidget(self._login_button)
        card_layout.addSpacing(12)

        # Sem "esqueci minha senha" de propósito: não existe fluxo de e-mail
        # de recuperação (nem servidor de e-mail configurado). A troca de
        # senha de um usuário é sempre feita pelo próprio admin da empresa,
        # editando o usuário na tela Usuários — campo "Nova senha" em
        # `UserDialog` (deixar em branco mantém a senha atual) — nunca
        # self-service a partir da tela de login.
        activate_license = QPushButton("Recebeu uma chave de ativação? Ative aqui")
        activate_license.setObjectName("LinkButton")
        activate_license.setCursor(Qt.CursorShape.PointingHandCursor)
        activate_license.clicked.connect(self._handle_activate_license_clicked)
        card_layout.addWidget(activate_license, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._email_input.returnPressed.connect(self._handle_login_clicked)
        self._password_input.returnPressed.connect(self._handle_login_clicked)
        self._email_input.setFocus()

        return card

    # --- ações ---

    def _handle_toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        self._apply_theme_callback(dark=self._dark_mode)
        self._theme_button.setText("☀️" if self._dark_mode else "🌙")

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
        self._apply_login_result(result)
        self._on_login_success()

    def _handle_login_failed(self, exc: Exception) -> None:
        self._set_loading(False)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Ocorreu um erro inesperado."
        self._show_error(message)

    def _apply_login_result(self, result: dict) -> None:
        """Same token/user/license shape whether it came from `POST /auth/
        login` or from activating a brand-new license (`ActivationDialog`,
        `POST /api/v1/activation/activate`) — one place populates the
        session either way, so the two entry points never drift apart.
        """
        user = result["user"]
        license_ = result.get("license")

        self._session.access_token = result["access_token"]
        self._session.refresh_token = result["refresh_token"]
        self._session.user_id = user["id"]
        self._session.email = user["email"]
        self._session.full_name = user["full_name"]
        self._session.phone = user.get("phone")
        self._session.tenant_id = user["tenant_id"]
        self._session.tenant_name = user.get("tenant_name")
        self._session.roles = user["roles"]
        self._session.permissions = user["permissions"]
        if license_:
            self._session.license_status = license_["status"]
            self._session.license_plan_code = license_["plan_code"]
            self._session.license_expires_at = license_["expires_at"]

    def _handle_activate_license_clicked(self) -> None:
        dialog = ActivationDialog(self._api_client)
        if dialog.exec() and dialog.login_result:
            self._apply_login_result(dialog.login_result)
            self._on_login_success()

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
