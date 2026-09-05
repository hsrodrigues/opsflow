"""Edit-license dialog for a tenant (seção 54/6/7) — trocar de plano,
mudar o status (suspender/reativar) e sobrescrever os limites de
usuários/veículos, sempre agindo sobre a licença mais recente da empresa.
"""
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.widgets import build_dialog_buttons, build_dialog_header

_PLAN_OPTIONS = [
    ("Starter", "STARTER"), ("Professional", "PROFESSIONAL"), ("Business", "BUSINESS"), ("Enterprise", "ENTERPRISE"),
]
_STATUS_OPTIONS = [
    ("Ativa", "ACTIVE"), ("Em teste", "TRIAL"), ("Suspensa", "SUSPENDED"),
    ("Expirada", "EXPIRED"), ("Cancelada", "CANCELLED"),
]


class TenantLicenseDialog(QDialog):
    def __init__(self, api_client: ApiClient, access_token: str, tenant: dict) -> None:
        super().__init__()
        self._api_client = api_client
        self._access_token = access_token
        self._tenant = tenant
        self._worker: ApiWorker | None = None
        self.saved_tenant: dict | None = None

        self.setWindowTitle(f"Licença — {tenant['legal_name']}")
        self.setMinimumWidth(420)
        self._build_ui()
        self._fill_from_tenant(tenant)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)

        layout.addWidget(build_dialog_header(
            "🔑", "IconChipInfo", "Alterar licença", self._tenant["legal_name"],
        ))
        layout.addSpacing(18)

        self._error_label = QLabel("")
        self._error_label.setObjectName("ErrorBanner")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        form = QFormLayout()
        form.setSpacing(10)

        # Código de ativação (seção 6): só quem opera a plataforma vê ou
        # gera isto — a própria empresa nunca precisa (nem consegue, pela
        # API) enxergar sua chave, só usar o sistema já ativado.
        key_row = QHBoxLayout()
        self._key_input = QLineEdit()
        self._key_input.setReadOnly(True)
        key_row.addWidget(self._key_input, stretch=1)
        regenerate_button = QPushButton("Gerar nova chave", objectName="LinkButton")
        regenerate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        regenerate_button.clicked.connect(self._handle_regenerate_key_clicked)
        key_row.addWidget(regenerate_button)
        form.addRow("Chave de ativação", key_row)

        self._plan_combo = QComboBox()
        for label, _value in _PLAN_OPTIONS:
            self._plan_combo.addItem(label)
        form.addRow("Plano", self._plan_combo)
        plan_hint = QLabel(
            "Trocar o plano só muda os limites que estiverem em \"Usar do plano\" "
            "abaixo — um limite customizado continua valendo no plano novo.",
            objectName="Faint",
        )
        plan_hint.setWordWrap(True)
        form.addRow("", plan_hint)

        self._status_combo = QComboBox()
        for label, _value in _STATUS_OPTIONS:
            self._status_combo.addItem(label)
        form.addRow("Status", self._status_combo)

        expires_row = QHBoxLayout()
        self._expires_input = QDateTimeEdit()
        self._expires_input.setCalendarPopup(True)
        self._expires_input.setDisplayFormat("dd/MM/yyyy HH:mm")
        expires_row.addWidget(self._expires_input, stretch=1)
        # Assinatura anual, não licença vitalícia — "todo ano tem que pagar
        # licença" — então a ação de referência aqui é renovar por +1 ano a
        # partir de hoje (nunca da data antiga, senão renovar uma licença já
        # vencida não teria efeito nenhum), não abrir mão da expiração.
        renew_button = QPushButton("Renovar +1 ano", objectName="LinkButton")
        renew_button.setCursor(Qt.CursorShape.PointingHandCursor)
        renew_button.clicked.connect(self._handle_renew_clicked)
        expires_row.addWidget(renew_button)
        form.addRow("Válida até", expires_row)

        self._max_users_input = QSpinBox()
        self._max_users_input.setRange(0, 100_000)
        self._max_users_input.setSpecialValueText("Usar do plano")
        form.addRow("Limite de usuários", self._max_users_input)
        self._users_effective_label = QLabel("", objectName="Muted")
        form.addRow("", self._users_effective_label)

        self._max_vehicles_input = QSpinBox()
        self._max_vehicles_input.setRange(0, 100_000)
        self._max_vehicles_input.setSpecialValueText("Usar do plano")
        form.addRow("Limite de veículos", self._max_vehicles_input)
        self._vehicles_effective_label = QLabel("", objectName="Muted")
        form.addRow("", self._vehicles_effective_label)

        layout.addLayout(form)
        layout.addSpacing(8)

        buttons = build_dialog_buttons("Salvar")
        buttons.accepted.connect(self._handle_save_clicked)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

    def _fill_from_tenant(self, tenant: dict) -> None:
        self._key_input.setText(tenant.get("license_key") or "—")
        plan_index = next((i for i, (_l, code) in enumerate(_PLAN_OPTIONS) if code == tenant.get("plan_code")), 0)
        self._plan_combo.setCurrentIndex(plan_index)
        status_index = next(
            (i for i, (_l, code) in enumerate(_STATUS_OPTIONS) if code == tenant.get("license_status")), 0,
        )
        self._status_combo.setCurrentIndex(status_index)
        if tenant.get("license_expires_at"):
            self._expires_input.setDateTime(QDateTime.fromString(tenant["license_expires_at"][:19], "yyyy-MM-ddTHH:mm:ss"))
        else:
            self._expires_input.setDateTime(QDateTime.currentDateTime().addYears(1))
        # `_override` (bruto, `None` quando não há), não `max_users`/
        # `max_vehicles` (já resolvidos pro plano atual) — senão trocar de
        # plano sem mexer nestes campos "congela" o limite do plano ANTIGO
        # como override do novo, ao salvar (bug real reportado pelo
        # usuário). "Usar do plano" (0) só aparece quando não há override
        # de verdade.
        self._max_users_input.setValue(tenant.get("max_users_override") or 0)
        self._max_vehicles_input.setValue(tenant.get("max_vehicles_override") or 0)
        self._users_effective_label.setText(f"Em vigor hoje: {tenant.get('max_users') or 'sem limite'}")
        self._vehicles_effective_label.setText(f"Em vigor hoje: {tenant.get('max_vehicles') or 'sem limite'}")

    def _handle_renew_clicked(self) -> None:
        now = QDateTime.currentDateTime()
        base = self._expires_input.dateTime()
        # Renovar uma licença já vencida a partir da data antiga não
        # estenderia o acesso de verdade (ainda estaria no passado) — parte
        # de "agora" nesse caso, e da própria data atual só quando ela ainda
        # está no futuro (renovação antecipada empilha o ano certinho).
        self._expires_input.setDateTime((base if base > now else now).addYears(1))

    def _handle_save_clicked(self) -> None:
        payload = {
            "plan_code": _PLAN_OPTIONS[self._plan_combo.currentIndex()][1],
            "status": _STATUS_OPTIONS[self._status_combo.currentIndex()][1],
            "expires_at": self._expires_input.dateTime().toString("yyyy-MM-ddTHH:mm:ss"),
            "max_users": self._max_users_input.value() or None,
            "max_vehicles": self._max_vehicles_input.value() or None,
        }
        self._buttons.setEnabled(False)
        self._worker = ApiWorker(
            self._api_client.update_tenant_license, self._access_token, self._tenant["id"], payload,
        )
        self._worker.succeeded.connect(self._handle_save_succeeded)
        self._worker.failed.connect(self._handle_save_failed)
        self._worker.start()

    def _handle_regenerate_key_clicked(self) -> None:
        confirmation = QMessageBox.question(
            self, "Gerar nova chave",
            "A chave atual deixará de ser válida. Tem certeza que deseja gerar uma nova chave de ativação?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        self._key_worker = ApiWorker(
            self._api_client.regenerate_license_key, self._access_token, self._tenant["id"],
        )
        self._key_worker.succeeded.connect(self._handle_regenerate_key_succeeded)
        self._key_worker.failed.connect(self._handle_save_failed)
        self._key_worker.start()

    def _handle_regenerate_key_succeeded(self, result: dict) -> None:
        self._tenant = result
        self._key_input.setText(result.get("license_key") or "—")

    def _handle_save_succeeded(self, result: dict) -> None:
        self.saved_tenant = result
        self.accept()

    def _handle_save_failed(self, exc: Exception) -> None:
        self._buttons.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível atualizar a licença."
        self._show_error(message)

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.show()
