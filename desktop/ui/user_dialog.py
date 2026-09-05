"""Create/edit dialog for a team member (seção 4/5).

E-mail é o identificador de login — trancado para edição depois de criado
(não existe fluxo de reconfirmação de e-mail neste MVP, então trocá-lo por
aqui deixaria a conta num estado ambíguo). Trocar a senha é uma ação
separada e opcional dentro do mesmo diálogo, em vez de uma tela à parte —
deixar em branco mantém a senha atual.
"""
from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.widgets import build_dialog_buttons, build_dialog_header
from utils.masks import bind_live_format, format_phone

_STATUS_OPTIONS = ["ATIVO", "INATIVO", "BLOQUEADO"]
_ROLE_OPTIONS = [
    ("Administrador", "ADMIN_EMPRESA"), ("Supervisor", "SUPERVISOR"),
    ("Operador", "OPERADOR"), ("Visualizador", "VISUALIZADOR"),
]


class UserDialog(QDialog):
    """Modal form to invite a new team member or edit an existing one."""

    def __init__(self, api_client: ApiClient, access_token: str, user: dict | None = None) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._user = user
        self._worker: ApiWorker | None = None
        self._password_worker: ApiWorker | None = None
        self.saved_user: dict | None = None

        self.setWindowTitle("Editar usuário" if user else "Novo usuário")
        self.setMinimumWidth(420)
        self._build_ui()
        if user:
            self._fill_from_user(user)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        layout.addWidget(build_dialog_header(
            "👤", "IconChipInfo",
            "Editar usuário" if self._user else "Novo usuário",
            "Acesso de um colega da sua equipe ao OpsFlow",
        ))
        layout.addSpacing(18)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Nome completo")
        form.addRow("Nome *", self._name_input)

        self._email_input = QLineEdit()
        self._email_input.setPlaceholderText("nome@empresa.com")
        self._email_input.setEnabled(self._user is None)
        form.addRow("E-mail *", self._email_input)

        self._phone_input = QLineEdit()
        self._phone_input.setPlaceholderText("(00) 00000-0000")
        self._phone_input.setMaxLength(16)
        bind_live_format(self._phone_input, format_phone)
        form.addRow("Telefone", self._phone_input)

        self._role_combo = QComboBox()
        for label, _value in _ROLE_OPTIONS:
            self._role_combo.addItem(label)
        form.addRow("Papel *", self._role_combo)

        if self._user is None:
            self._password_input = QLineEdit()
            self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._password_input.setPlaceholderText("Mínimo 8 caracteres")
            form.addRow("Senha *", self._password_input)
            self._new_password_input = None
        else:
            self._password_input = None
            self._new_password_input = QLineEdit()
            self._new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._new_password_input.setPlaceholderText("Deixe em branco para manter a atual")
            form.addRow("Nova senha", self._new_password_input)

            self._status_combo = QComboBox()
            self._status_combo.addItems(_STATUS_OPTIONS)
            form.addRow("Status", self._status_combo)

        layout.addLayout(form)
        layout.addSpacing(8)

        buttons = build_dialog_buttons("Salvar")
        buttons.accepted.connect(self._handle_save_clicked)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _fill_from_user(self, user: dict) -> None:
        self._name_input.setText(user["full_name"])
        self._email_input.setText(user["email"])
        self._phone_input.setText(user.get("phone") or "")
        role_index = next((i for i, (_l, code) in enumerate(_ROLE_OPTIONS) if code == user["role_code"]), 0)
        self._role_combo.setCurrentIndex(role_index)
        status_index = self._status_combo.findText(user.get("status", "ATIVO"))
        if status_index >= 0:
            self._status_combo.setCurrentIndex(status_index)

    def _handle_save_clicked(self) -> None:
        full_name = self._name_input.text().strip()
        email = self._email_input.text().strip()
        if not full_name or not email:
            self._show_error("Informe nome e e-mail.")
            return
        if self._user is None and len((self._password_input.text() or "")) < 8:
            self._show_error("A senha precisa ter pelo menos 8 caracteres.")
            return

        role_code = _ROLE_OPTIONS[self._role_combo.currentIndex()][1]
        self._buttons.setEnabled(False)

        if self._user is None:
            payload = {
                "full_name": full_name, "email": email, "phone": self._phone_input.text().strip() or None,
                "role_code": role_code, "password": self._password_input.text(),
            }
            self._worker = ApiWorker(self._api_client.create_user, self._access_token, payload)
        else:
            payload = {
                "full_name": full_name, "phone": self._phone_input.text().strip() or None,
                "role_code": role_code, "status": self._status_combo.currentText(),
            }
            self._worker = ApiWorker(self._api_client.update_user, self._access_token, self._user["id"], payload)
        self._worker.succeeded.connect(self._handle_save_succeeded)
        self._worker.failed.connect(self._handle_save_failed)
        self._worker.start()

    def _handle_save_succeeded(self, result: dict) -> None:
        self.saved_user = result
        new_password = self._new_password_input.text() if self._new_password_input else ""
        if new_password:
            if len(new_password) < 8:
                self._buttons.setEnabled(True)
                self._show_error("Usuário salvo, mas a nova senha precisa ter pelo menos 8 caracteres.")
                return
            self._password_worker = ApiWorker(
                self._api_client.reset_user_password, self._access_token, self._user["id"], new_password,
            )
            self._password_worker.succeeded.connect(lambda _r: self.accept())
            self._password_worker.failed.connect(self._handle_save_failed)
            self._password_worker.start()
            return
        self.accept()

    def _handle_save_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível salvar o usuário."
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
