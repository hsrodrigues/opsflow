"""Create/edit dialog for a carrier (seção 11)."""
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from utils.masks import bind_live_format, format_cnpj, format_phone

_STATUS_OPTIONS = ["ATIVO", "INATIVO", "BLOQUEADO"]


class CarrierDialog(QDialog):
    """Modal form to create a new carrier or edit an existing one."""

    def __init__(self, api_client: ApiClient, access_token: str, carrier: dict | None = None) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._carrier = carrier
        self._worker: ApiWorker | None = None
        self.saved_carrier: dict | None = None

        self.setWindowTitle("Editar transportadora" if carrier else "Nova transportadora")
        self.setMinimumWidth(440)
        self._build_ui()
        if carrier:
            self._fill_from_carrier(carrier)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        form = QFormLayout()
        form.setSpacing(10)

        self._legal_name_input = QLineEdit()
        form.addRow("Razão social *", self._legal_name_input)

        self._trade_name_input = QLineEdit()
        form.addRow("Nome fantasia", self._trade_name_input)

        self._cnpj_input = QLineEdit()
        self._cnpj_input.setPlaceholderText("00.000.000/0000-00")
        self._cnpj_input.setMaxLength(18)
        bind_live_format(self._cnpj_input, format_cnpj)
        form.addRow("CNPJ", self._cnpj_input)

        self._contact_name_input = QLineEdit()
        form.addRow("Contato", self._contact_name_input)

        self._phone_input = QLineEdit()
        self._phone_input.setPlaceholderText("(00) 00000-0000")
        self._phone_input.setMaxLength(16)
        bind_live_format(self._phone_input, format_phone)
        form.addRow("Telefone", self._phone_input)

        self._email_input = QLineEdit()
        form.addRow("E-mail", self._email_input)

        self._status_combo = QComboBox()
        self._status_combo.addItems(_STATUS_OPTIONS)
        self._status_combo.setEnabled(self._carrier is not None)
        form.addRow("Status", self._status_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("PrimaryButton")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("SecondaryButton")
        buttons.accepted.connect(self._handle_save_clicked)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _fill_from_carrier(self, carrier: dict) -> None:
        self._legal_name_input.setText(carrier["legal_name"])
        self._trade_name_input.setText(carrier.get("trade_name") or "")
        self._cnpj_input.setText(carrier.get("cnpj") or "")
        self._contact_name_input.setText(carrier.get("contact_name") or "")
        self._phone_input.setText(carrier.get("phone") or "")
        self._email_input.setText(carrier.get("email") or "")
        status_index = self._status_combo.findText(carrier.get("status", "ATIVO"))
        if status_index >= 0:
            self._status_combo.setCurrentIndex(status_index)

    def _handle_save_clicked(self) -> None:
        legal_name = self._legal_name_input.text().strip()
        if not legal_name:
            self._show_error("Informe a razão social da transportadora.")
            return

        payload = {
            "legal_name": legal_name,
            "trade_name": self._trade_name_input.text().strip() or None,
            "cnpj": self._cnpj_input.text().strip() or None,
            "contact_name": self._contact_name_input.text().strip() or None,
            "phone": self._phone_input.text().strip() or None,
            "email": self._email_input.text().strip() or None,
        }
        if self._carrier is not None:
            payload["status"] = self._status_combo.currentText()

        self._buttons.setEnabled(False)
        if self._carrier is None:
            self._worker = ApiWorker(self._api_client.create_carrier, self._access_token, payload)
        else:
            self._worker = ApiWorker(
                self._api_client.update_carrier, self._access_token, self._carrier["id"], payload
            )
        self._worker.succeeded.connect(self._handle_save_succeeded)
        self._worker.failed.connect(self._handle_save_failed)
        self._worker.start()

    def _handle_save_succeeded(self, result: dict) -> None:
        self.saved_carrier = result
        self.accept()

    def _handle_save_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível salvar a transportadora."
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
