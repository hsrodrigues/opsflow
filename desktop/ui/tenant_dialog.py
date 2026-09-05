"""Onboarding dialog for a new tenant (seção 54) — cria a empresa, a
licença TRIAL inicial e o primeiro usuário ADMIN_EMPRESA numa única
chamada, porque é assim que esse fluxo acontece de verdade: ninguém cria
uma empresa sem ninguém pra administrá-la.
"""
from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QLabel, QLineEdit, QSpinBox, QVBoxLayout

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.widgets import build_dialog_buttons, build_dialog_header
from utils.masks import bind_live_format, format_cnpj

_PLAN_OPTIONS = [
    ("Starter", "STARTER"), ("Professional", "PROFESSIONAL"), ("Business", "BUSINESS"), ("Enterprise", "ENTERPRISE"),
]


class TenantDialog(QDialog):
    """Modal form to onboard a new tenant company."""

    def __init__(self, api_client: ApiClient, access_token: str) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._worker: ApiWorker | None = None
        self.saved_tenant: dict | None = None

        self.setWindowTitle("Nova empresa")
        self.setMinimumWidth(440)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        layout.addWidget(build_dialog_header(
            "🏭", "IconChipInfo", "Nova empresa",
            "Cadastra a empresa, a licença de teste e o primeiro administrador",
        ))
        layout.addSpacing(18)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        form = QFormLayout()
        form.setSpacing(10)

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

        self._plan_combo = QComboBox()
        for label, _value in _PLAN_OPTIONS:
            self._plan_combo.addItem(label)
        form.addRow("Plano inicial *", self._plan_combo)

        self._trial_days_input = QSpinBox()
        self._trial_days_input.setRange(1, 365)
        self._trial_days_input.setValue(30)
        self._trial_days_input.setSuffix(" dias")
        form.addRow("Duração do teste", self._trial_days_input)

        self._admin_name_input = QLineEdit()
        self._admin_name_input.setPlaceholderText("Nome do administrador")
        form.addRow("Administrador *", self._admin_name_input)

        self._admin_email_input = QLineEdit()
        self._admin_email_input.setPlaceholderText("admin@empresa.com")
        form.addRow("E-mail do administrador *", self._admin_email_input)

        self._admin_password_input = QLineEdit()
        self._admin_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._admin_password_input.setPlaceholderText("Mínimo 8 caracteres")
        form.addRow("Senha inicial *", self._admin_password_input)

        layout.addLayout(form)
        layout.addSpacing(8)

        buttons = build_dialog_buttons("Criar empresa")
        buttons.accepted.connect(self._handle_save_clicked)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _handle_save_clicked(self) -> None:
        legal_name = self._legal_name_input.text().strip()
        admin_name = self._admin_name_input.text().strip()
        admin_email = self._admin_email_input.text().strip()
        admin_password = self._admin_password_input.text()
        if not legal_name or not admin_name or not admin_email:
            self._show_error("Informe razão social, nome e e-mail do administrador.")
            return
        if len(admin_password) < 8:
            self._show_error("A senha do administrador precisa ter pelo menos 8 caracteres.")
            return

        payload = {
            "legal_name": legal_name, "trade_name": self._trade_name_input.text().strip() or None,
            "cnpj": self._cnpj_input.text().strip() or None,
            "plan_code": _PLAN_OPTIONS[self._plan_combo.currentIndex()][1],
            "trial_days": self._trial_days_input.value(),
            "admin_full_name": admin_name, "admin_email": admin_email, "admin_password": admin_password,
        }
        self._buttons.setEnabled(False)
        self._worker = ApiWorker(self._api_client.create_tenant, self._access_token, payload)
        self._worker.succeeded.connect(self._handle_save_succeeded)
        self._worker.failed.connect(self._handle_save_failed)
        self._worker.start()

    def _handle_save_succeeded(self, result: dict) -> None:
        self.saved_tenant = result
        self.accept()

    def _handle_save_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível criar a empresa."
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
