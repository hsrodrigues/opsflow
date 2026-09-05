"""Create/edit dialog for a product — o catálogo do que é transportado.

Existia antes só como texto livre em "Carga" na Programação, o que deixava
a Quantidade sem unidade declarada em lugar nenhum. Cada produto aqui já
declara sua própria unidade — a Programação passa a mostrar essa unidade ao
lado da quantidade em vez do usuário ter que adivinhar ou converter na mão.
"""
from PySide6.QtWidgets import QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.widgets import build_dialog_buttons, build_dialog_header

_STATUS_OPTIONS = ["ATIVO", "INATIVO"]
_UNIT_OPTIONS = [
    ("Unidade", "UNIDADE"), ("Quilograma (kg)", "KG"), ("Tonelada (t)", "TONELADA"),
    ("Litro (L)", "LITRO"), ("Caixa", "CAIXA"), ("Palete", "PALETE"), ("Metro cúbico (m³)", "METRO_CUBICO"),
]


class ProductDialog(QDialog):
    """Modal form to create a new product or edit an existing one."""

    def __init__(self, api_client: ApiClient, access_token: str, product: dict | None = None) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._product = product
        self._worker: ApiWorker | None = None
        self.saved_product: dict | None = None

        self.setWindowTitle("Editar produto" if product else "Novo produto")
        self.setMinimumWidth(420)
        self._build_ui()
        if product:
            self._fill_from_product(product)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        layout.addWidget(build_dialog_header(
            "📦", "IconChipInfo",
            "Editar produto" if self._product else "Novo produto",
            "Item do catálogo transportado, com sua unidade de medida",
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
        self._name_input.setPlaceholderText("Ex.: Cimento CP-II")
        form.addRow("Nome *", self._name_input)

        self._sku_input = QLineEdit()
        self._sku_input.setPlaceholderText("Opcional")
        form.addRow("SKU / Código", self._sku_input)

        self._unit_combo = QComboBox()
        for label, _value in _UNIT_OPTIONS:
            self._unit_combo.addItem(label)
        form.addRow("Unidade de medida *", self._unit_combo)

        self._weight_input = QDoubleSpinBox()
        self._weight_input.setRange(0, 1_000_000)
        self._weight_input.setDecimals(3)
        self._weight_input.setSuffix(" kg")
        self._weight_input.setSpecialValueText("—")
        form.addRow("Peso padrão (opcional)", self._weight_input)

        self._status_combo = QComboBox()
        self._status_combo.addItems(_STATUS_OPTIONS)
        self._status_combo.setEnabled(self._product is not None)
        form.addRow("Status", self._status_combo)

        layout.addLayout(form)
        layout.addSpacing(8)

        buttons = build_dialog_buttons("Salvar")
        buttons.accepted.connect(self._handle_save_clicked)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _fill_from_product(self, product: dict) -> None:
        self._name_input.setText(product["name"])
        self._sku_input.setText(product.get("sku") or "")
        unit_index = next(
            (i for i, (_label, value) in enumerate(_UNIT_OPTIONS) if value == product.get("unit_of_measure")), 0,
        )
        self._unit_combo.setCurrentIndex(unit_index)
        self._weight_input.setValue(product.get("default_weight_kg") or 0)
        status_index = self._status_combo.findText(product.get("status", "ATIVO"))
        if status_index >= 0:
            self._status_combo.setCurrentIndex(status_index)

    def _handle_save_clicked(self) -> None:
        name = self._name_input.text().strip()
        if not name:
            self._show_error("Informe o nome do produto.")
            return

        payload = {
            "name": name,
            "sku": self._sku_input.text().strip() or None,
            "unit_of_measure": _UNIT_OPTIONS[self._unit_combo.currentIndex()][1],
            "default_weight_kg": self._weight_input.value() or None,
        }
        if self._product is not None:
            payload["status"] = self._status_combo.currentText()

        self._buttons.setEnabled(False)
        if self._product is None:
            self._worker = ApiWorker(self._api_client.create_product, self._access_token, payload)
        else:
            self._worker = ApiWorker(
                self._api_client.update_product, self._access_token, self._product["id"], payload
            )
        self._worker.succeeded.connect(self._handle_save_succeeded)
        self._worker.failed.connect(self._handle_save_failed)
        self._worker.start()

    def _handle_save_succeeded(self, result: dict) -> None:
        self.saved_product = result
        self.accept()

    def _handle_save_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível salvar o produto."
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
