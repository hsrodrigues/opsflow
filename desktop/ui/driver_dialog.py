"""Create/edit dialog for a driver (seção 10)."""
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError

_STATUS_OPTIONS = ["ATIVO", "INATIVO", "BLOQUEADO"]
_CNH_CATEGORIES = ["", "A", "B", "AB", "C", "D", "E"]


class DriverDialog(QDialog):
    """Modal form to create a new driver or edit an existing one."""

    def __init__(self, api_client: ApiClient, access_token: str, carriers: list[dict], driver: dict | None = None) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._carriers = carriers
        self._driver = driver
        self._worker: ApiWorker | None = None
        self.saved_driver: dict | None = None

        self.setWindowTitle("Editar motorista" if driver else "Novo motorista")
        self.setMinimumWidth(420)
        self._build_ui()
        if driver:
            self._fill_from_driver(driver)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_input = QLineEdit()
        form.addRow("Nome completo *", self._name_input)

        self._cpf_input = QLineEdit()
        self._cpf_input.setPlaceholderText("000.000.000-00")
        form.addRow("CPF *", self._cpf_input)

        self._cnh_number_input = QLineEdit()
        form.addRow("Nº da CNH", self._cnh_number_input)

        self._cnh_category_combo = QComboBox()
        self._cnh_category_combo.addItems(_CNH_CATEGORIES)
        form.addRow("Categoria CNH", self._cnh_category_combo)

        self._cnh_expiry_input = QDateEdit()
        self._cnh_expiry_input.setCalendarPopup(True)
        self._cnh_expiry_input.setDisplayFormat("dd/MM/yyyy")
        self._cnh_expiry_input.setDate(QDate.currentDate().addYears(1))  # palpite razoável, não "vence hoje"
        self._cnh_expiry_input.setSpecialValueText(" ")
        form.addRow("Validade CNH", self._cnh_expiry_input)

        self._phone_input = QLineEdit()
        form.addRow("Telefone", self._phone_input)

        self._carrier_combo = QComboBox()
        self._carrier_combo.addItem("— Sem transportadora —", None)
        for carrier in self._carriers:
            self._carrier_combo.addItem(carrier["legal_name"], carrier["id"])
        form.addRow("Transportadora", self._carrier_combo)

        self._status_combo = QComboBox()
        self._status_combo.addItems(_STATUS_OPTIONS)
        self._status_combo.setEnabled(self._driver is not None)
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

    def _fill_from_driver(self, driver: dict) -> None:
        self._name_input.setText(driver["full_name"])
        self._cpf_input.setText(driver["cpf"])
        self._cnh_number_input.setText(driver.get("cnh_number") or "")
        if driver.get("cnh_category"):
            index = self._cnh_category_combo.findText(driver["cnh_category"])
            if index >= 0:
                self._cnh_category_combo.setCurrentIndex(index)
        if driver.get("cnh_expiry"):
            self._cnh_expiry_input.setDate(QDate.fromString(driver["cnh_expiry"], "yyyy-MM-dd"))
        self._phone_input.setText(driver.get("phone") or "")
        if driver.get("carrier_id") is not None:
            index = self._carrier_combo.findData(driver["carrier_id"])
            if index >= 0:
                self._carrier_combo.setCurrentIndex(index)
        status_index = self._status_combo.findText(driver.get("status", "ATIVO"))
        if status_index >= 0:
            self._status_combo.setCurrentIndex(status_index)

    def _handle_save_clicked(self) -> None:
        full_name = self._name_input.text().strip()
        cpf = self._cpf_input.text().strip()
        if not full_name or not cpf:
            self._show_error("Informe nome completo e CPF.")
            return

        payload = {
            "full_name": full_name,
            "cpf": cpf,
            "cnh_number": self._cnh_number_input.text().strip() or None,
            "cnh_category": self._cnh_category_combo.currentText() or None,
            "cnh_expiry": self._cnh_expiry_input.date().toString("yyyy-MM-dd"),
            "phone": self._phone_input.text().strip() or None,
            "carrier_id": self._carrier_combo.currentData(),
        }
        if self._driver is not None:
            payload["status"] = self._status_combo.currentText()

        self._buttons.setEnabled(False)
        if self._driver is None:
            self._worker = ApiWorker(self._api_client.create_driver, self._access_token, payload)
        else:
            self._worker = ApiWorker(self._api_client.update_driver, self._access_token, self._driver["id"], payload)
        self._worker.succeeded.connect(self._handle_save_succeeded)
        self._worker.failed.connect(self._handle_save_failed)
        self._worker.start()

    def _handle_save_succeeded(self, result: dict) -> None:
        self.saved_driver = result
        self.accept()

    def _handle_save_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível salvar o motorista."
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
