"""Activation dialog (seção 6) — um prospect sem conta nenhuma resgatando
uma chave que recebeu do SUPER_ADMIN: digita a chave + os dados da própria
empresa e sai logado, sem precisar de um passo de login separado (a API já
devolve o par de tokens de uma vez, ver `activation_service.
activate_license_key`).
"""
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.widgets import build_dialog_buttons, build_dialog_header
from utils.masks import bind_live_format, format_cnpj


class ActivationDialog(QDialog):
    """On success, `self.login_result` holds the same shape `ApiClient.login`
    returns — the caller (`LoginWindow`) treats it exactly like a login.
    """

    def __init__(self, api_client: ApiClient) -> None:
        super().__init__()
        self._api_client = api_client
        self._worker: ApiWorker | None = None
        self.login_result: dict | None = None

        self.setWindowTitle("Ativar licença")
        self.setMinimumWidth(440)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        layout.addWidget(build_dialog_header(
            "🎟️", "IconChipInfo", "Ativar licença",
            "Digite a chave que você recebeu e crie a conta da sua empresa",
        ))
        layout.addSpacing(18)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        form = QFormLayout()
        form.setSpacing(10)

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("Chave recebida")
        form.addRow("Chave de ativação *", self._key_input)

        self._legal_name_input = QLineEdit()
        self._legal_name_input.setPlaceholderText("Razão social")
        form.addRow("Razão social *", self._legal_name_input)

        self._trade_name_input = QLineEdit()
        self._trade_name_input.setPlaceholderText("Opcional")
        form.addRow("Nome fantasia", self._trade_name_input)

        self._cnpj_input = QLineEdit()
        self._cnpj_input.setPlaceholderText("00.000.000/0000-00")
        self._cnpj_input.setMaxLength(18)
        bind_live_format(self._cnpj_input, format_cnpj)
        form.addRow("CNPJ", self._cnpj_input)

        self._admin_name_input = QLineEdit()
        self._admin_name_input.setPlaceholderText("Seu nome")
        form.addRow("Seu nome *", self._admin_name_input)

        self._admin_email_input = QLineEdit()
        self._admin_email_input.setPlaceholderText("seuemail@empresa.com")
        form.addRow("Seu e-mail *", self._admin_email_input)

        self._admin_password_input = QLineEdit()
        self._admin_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._admin_password_input.setPlaceholderText("Mínimo 8 caracteres")
        form.addRow("Crie uma senha *", self._admin_password_input)

        layout.addLayout(form)
        layout.addSpacing(8)

        buttons = build_dialog_buttons("Ativar e entrar")
        buttons.accepted.connect(self._handle_activate_clicked)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _handle_activate_clicked(self) -> None:
        license_key = self._key_input.text().strip()
        legal_name = self._legal_name_input.text().strip()
        admin_name = self._admin_name_input.text().strip()
        admin_email = self._admin_email_input.text().strip()
        admin_password = self._admin_password_input.text()
        if not license_key or not legal_name or not admin_name or not admin_email:
            self._show_error("Preencha a chave, a razão social, seu nome e seu e-mail.")
            return
        if len(admin_password) < 8:
            self._show_error("A senha precisa ter pelo menos 8 caracteres.")
            return

        payload = {
            "license_key": license_key, "legal_name": legal_name,
            "trade_name": self._trade_name_input.text().strip() or None,
            "cnpj": self._cnpj_input.text().strip() or None,
            "admin_full_name": admin_name, "admin_email": admin_email, "admin_password": admin_password,
        }
        self._buttons.setEnabled(False)
        self._worker = ApiWorker(self._api_client.activate_license, payload)
        self._worker.succeeded.connect(self._handle_activate_succeeded)
        self._worker.failed.connect(self._handle_activate_failed)
        self._worker.start()

    def _handle_activate_succeeded(self, result: dict) -> None:
        self.login_result = result
        self.accept()

    def _handle_activate_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível ativar a licença."
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
