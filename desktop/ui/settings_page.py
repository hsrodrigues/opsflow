"""Settings screen (seção 26, "Configurações") — auto-atendimento: qualquer
usuário logado edita o próprio nome/telefone (`PATCH /api/v1/auth/me`), sem
depender da permissão `users.manage` que só admins têm (essa segue exclusiva
da tela Usuários, e só pra editar OUTRAS pessoas). Não tem campo de senha de
propósito: nunca existiu um fluxo de "esqueci minha senha" self-service
nesse produto, e a decisão foi não criar um — trocar a própria senha (ou a
de qualquer outro usuário) é sempre uma ação do admin da empresa, editando o
usuário na tela Usuários.
"""
from PySide6.QtWidgets import QFrame, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.config import DesktopConfig
from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.theme import apply_shadow
from ui.widgets import build_badge
from utils.masks import bind_live_format, format_phone

_ROLE_LABELS = {
    "SUPER_ADMIN": "Administrador da Plataforma", "ADMIN_EMPRESA": "Administrador",
    "SUPERVISOR": "Supervisor", "OPERADOR": "Operador", "VISUALIZADOR": "Visualizador",
}


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class SettingsPage(QWidget):
    def __init__(self, config: DesktopConfig, api_client: ApiClient, session: UserSession) -> None:
        super().__init__()
        self._config = config
        self._api_client = api_client
        self._session = session
        self._worker: ApiWorker | None = None

        self._build_ui()
        self._load_current_values()
        self._load_connection_status()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        layout.addWidget(QLabel("Configurações", objectName="PageTitle"))
        layout.addWidget(QLabel("Suas informações de conta neste sistema", objectName="Muted"))

        self._status_message = QLabel("")
        self._status_message.setObjectName("Muted")
        self._status_message.hide()
        layout.addWidget(self._status_message)

        # --- cartão "Meu perfil" ---
        profile_card = QFrame(objectName="Card")
        apply_shadow(profile_card, blur=20, y_offset=6, alpha=16)
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.setContentsMargins(20, 18, 20, 18)
        profile_layout.setSpacing(14)

        header_row = QVBoxLayout()
        header_row.setSpacing(2)
        header_row.addWidget(QLabel("Meu perfil", objectName="SectionTitle"))
        header_row.addWidget(
            QLabel("Essas informações aparecem para o resto da sua equipe.", objectName="Muted")
        )
        profile_layout.addLayout(header_row)

        form = QFormLayout()
        form.setSpacing(10)

        self._email_value = QLabel("—", objectName="Muted")
        form.addRow("E-mail", self._email_value)
        form.addRow("Papel", self._build_role_badge_holder())

        self._full_name_input = QLineEdit()
        self._full_name_input.setPlaceholderText("Seu nome completo")
        form.addRow("Nome completo *", self._full_name_input)

        self._phone_input = QLineEdit()
        self._phone_input.setPlaceholderText("(00) 00000-0000")
        self._phone_input.setMaxLength(15)
        bind_live_format(self._phone_input, format_phone)
        form.addRow("Telefone", self._phone_input)

        profile_layout.addLayout(form)

        save_row = QVBoxLayout()
        self._save_button = QPushButton("Salvar alterações", objectName="PrimaryButton")
        self._save_button.clicked.connect(self._handle_save_clicked)
        save_row.addWidget(self._save_button)
        profile_layout.addLayout(save_row)

        layout.addWidget(profile_card)

        # --- cartão "Senha" — sem campo de senha nenhum, de propósito ---
        password_card = QFrame(objectName="Card")
        apply_shadow(password_card, blur=20, y_offset=6, alpha=16)
        password_layout = QVBoxLayout(password_card)
        password_layout.setContentsMargins(20, 18, 20, 18)
        password_layout.setSpacing(4)
        password_layout.addWidget(QLabel("Senha de acesso", objectName="SectionTitle"))
        note = QLabel(
            "Por segurança, a troca de senha é feita pelo administrador da sua empresa, "
            "editando o seu usuário na tela Usuários — não existe um fluxo de \"esqueci "
            "minha senha\" pelo próprio login. Se você esqueceu a sua, peça para o "
            "administrador definir uma nova."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        password_layout.addWidget(note)
        layout.addWidget(password_card)

        # --- cartão "Sobre" ---
        about_card = QFrame(objectName="Card")
        apply_shadow(about_card, blur=20, y_offset=6, alpha=16)
        about_layout = QFormLayout(about_card)
        about_layout.setContentsMargins(20, 18, 20, 18)
        about_layout.setSpacing(8)
        about_layout.addRow(QLabel("Sobre o sistema", objectName="SectionTitle"))
        about_layout.addRow("Versão", QLabel(self._config.app_version, objectName="Muted"))
        about_layout.addRow("Servidor", QLabel(self._config.api_base_url, objectName="Muted"))
        self._database_value = QLabel("Consultando...", objectName="Muted")
        about_layout.addRow("Banco de dados", self._database_value)
        connection_holder = QWidget()
        self._connection_status_slot = QVBoxLayout(connection_holder)
        self._connection_status_slot.setContentsMargins(0, 0, 0, 0)
        about_layout.addRow("Status da conexão", connection_holder)
        layout.addWidget(about_card)

        layout.addStretch(1)

    def _build_role_badge_holder(self) -> QWidget:
        holder = QWidget()
        self._role_badge_layout = QVBoxLayout(holder)
        self._role_badge_layout.setContentsMargins(0, 0, 0, 0)
        return holder

    def _load_current_values(self) -> None:
        self._email_value.setText(self._session.email or "—")
        self._full_name_input.setText(self._session.full_name or "")
        if self._session.phone:
            self._phone_input.setText(self._session.phone)

        primary_role = self._session.roles[0] if self._session.roles else None
        role_label = _ROLE_LABELS.get(primary_role, primary_role or "—")
        self._role_badge_layout.addWidget(build_badge(role_label, "BadgeNeutral"))

    def _load_connection_status(self) -> None:
        # `/api/health` não exige token — checagem simples de conectividade,
        # a mesma rota que já alimenta o indicador 🟢/🔴 do topbar (seção 32),
        # só que agora também mostrando EM QUAL banco (host) o backend está
        # falando de verdade. Pedido depois de mais de uma confusão nesta
        # sessão sobre "qual banco tá ativo agora" (local vs. nuvem).
        self._health_worker = ApiWorker(self._api_client.check_health)
        self._health_worker.succeeded.connect(self._handle_connection_status_succeeded)
        self._health_worker.failed.connect(self._handle_connection_status_failed)
        self._health_worker.start()

    def _handle_connection_status_succeeded(self, result: dict) -> None:
        self._database_value.setText(result.get("database_host") or "—")
        database_up = result.get("database") == "up"
        text = "Conectado" if database_up else "Sem conexão com o banco"
        badge_class = "BadgeSuccess" if database_up else "BadgeDanger"
        self._set_connection_badge(text, badge_class)

    def _handle_connection_status_failed(self, _exc: Exception) -> None:
        self._database_value.setText("—")
        self._set_connection_badge("Servidor inacessível", "BadgeDanger")

    def _set_connection_badge(self, text: str, badge_class: str) -> None:
        while self._connection_status_slot.count():
            item = self._connection_status_slot.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._connection_status_slot.addWidget(build_badge(text, badge_class))

    def _handle_save_clicked(self) -> None:
        full_name = self._full_name_input.text().strip()
        if not full_name:
            self._show_status("Informe seu nome completo.", is_error=True)
            return

        payload = {"full_name": full_name, "phone": self._phone_input.text().strip() or None}
        self._save_button.setEnabled(False)
        self._worker = ApiWorker(self._api_client.update_my_profile, self._session.access_token, payload)
        self._worker.succeeded.connect(self._handle_save_succeeded)
        self._worker.failed.connect(self._handle_save_failed)
        self._worker.start()

    def _handle_save_succeeded(self, user: dict) -> None:
        self._save_button.setEnabled(True)
        self._session.full_name = user["full_name"]
        self._session.phone = user.get("phone")
        self._show_status("Perfil atualizado com sucesso.")

    def _handle_save_failed(self, exc: Exception) -> None:
        self._save_button.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível salvar suas alterações."
        self._show_status(message, is_error=True)

    def _show_status(self, message: str, *, is_error: bool = False) -> None:
        self._status_message.setObjectName("ErrorBanner" if is_error else "Muted")
        _repolish(self._status_message)
        self._status_message.setText(message)
        self._status_message.show()
