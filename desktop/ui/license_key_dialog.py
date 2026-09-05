"""Generate-license-key dialog (seção 6, console de plataforma) — o
`SUPER_ADMIN` escolhe só o plano e a duração do teste, sem saber ainda
quem vai comprar. A chave gerada aparece na tela pronta pra copiar e
repassar ao cliente, que a resgata sozinho (`ui/activation_dialog.py`).
"""
from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QLabel, QLineEdit, QSpinBox, QVBoxLayout

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.widgets import build_dialog_buttons, build_dialog_header

_PLAN_OPTIONS = [
    ("Starter", "STARTER"), ("Professional", "PROFESSIONAL"), ("Business", "BUSINESS"), ("Enterprise", "ENTERPRISE"),
]


class LicenseKeyDialog(QDialog):
    def __init__(self, api_client: ApiClient, access_token: str) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._worker: ApiWorker | None = None
        self._generated: dict | None = None

        self.setWindowTitle("Gerar chave de ativação")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        layout.addWidget(build_dialog_header(
            "🎟️", "IconChipInfo", "Gerar chave de ativação",
            "Sem empresa vinculada ainda — o cliente resgata sozinho",
        ))
        layout.addSpacing(18)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        self._form = QFormLayout()
        self._form.setSpacing(10)

        self._plan_combo = QComboBox()
        for label, _value in _PLAN_OPTIONS:
            self._plan_combo.addItem(label)
        self._form.addRow("Plano *", self._plan_combo)

        self._trial_days_input = QSpinBox()
        self._trial_days_input.setRange(1, 365)
        self._trial_days_input.setValue(30)
        self._trial_days_input.setSuffix(" dias")
        self._form.addRow("Duração do teste", self._trial_days_input)

        layout.addLayout(self._form)
        layout.addSpacing(8)

        self._generate_buttons = self._build_buttons("Gerar chave")
        self._generate_buttons.accepted.connect(self._handle_generate_clicked)
        self._generate_buttons.rejected.connect(self.reject)
        layout.addWidget(self._generate_buttons)
        self._layout = layout

    @staticmethod
    def _build_buttons(label: str):
        return build_dialog_buttons(label)

    def _handle_generate_clicked(self) -> None:
        payload = {
            "plan_code": _PLAN_OPTIONS[self._plan_combo.currentIndex()][1],
            "trial_days": self._trial_days_input.value(),
        }
        self._generate_buttons.setEnabled(False)
        self._worker = ApiWorker(self._api_client.generate_license_key, self._access_token, payload)
        self._worker.succeeded.connect(self._handle_generate_succeeded)
        self._worker.failed.connect(self._handle_generate_failed)
        self._worker.start()

    def _handle_generate_succeeded(self, result: dict) -> None:
        self._generated = result
        self._plan_combo.setEnabled(False)
        self._trial_days_input.setEnabled(False)

        key_row_label = QLabel("Chave gerada")
        key_input = QLineEdit(result["license_key"])
        key_input.setReadOnly(True)
        key_input.setCursorPosition(0)
        self._form.addRow(key_row_label, key_input)

        hint = QLabel("Copie e envie esta chave ao cliente — ele mesmo cria a conta com ela.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        self._layout.insertWidget(self._layout.count() - 1, hint)

        self._layout.removeWidget(self._generate_buttons)
        self._generate_buttons.deleteLater()
        close_buttons = build_dialog_buttons("Concluir")
        close_buttons.accepted.connect(self.accept)
        close_buttons.rejected.connect(self.accept)
        self._layout.addWidget(close_buttons)

    def _handle_generate_failed(self, exc: Exception) -> None:
        self._generate_buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível gerar a chave."
        self._error_label.setText(message)
        self._error_label.show()
