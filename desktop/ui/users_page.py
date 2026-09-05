"""Users screen (seção 4/5): gestão da equipe da empresa — convidar, editar
papel/dados, ativar/desativar. Sem exclusão de verdade (ver `users.py` no
backend) — uma conta é desativada, nunca apagada, pra preservar quem fez o
quê no histórico de auditoria.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.theme import apply_shadow
from ui.user_dialog import UserDialog
from ui.widgets import build_badge

_STATUS_FILTER_OPTIONS = [
    ("Todos os status", None), ("Ativo", "ATIVO"), ("Inativo", "INATIVO"), ("Bloqueado", "BLOQUEADO"),
]
_STATUS_DISPLAY = {
    "ATIVO": ("Ativo", "BadgeSuccess"), "INATIVO": ("Inativo", "BadgeNeutral"), "BLOQUEADO": ("Bloqueado", "BadgeDanger"),
}
_ROLE_LABELS = {
    "ADMIN_EMPRESA": "Administrador", "SUPERVISOR": "Supervisor", "OPERADOR": "Operador", "VISUALIZADOR": "Visualizador",
}
_PAGE_SIZE = 15


class UsersPage(QWidget):
    def __init__(self, api_client: ApiClient, session: UserSession) -> None:
        super().__init__()
        self._api_client = api_client
        self._session = session
        self._page = 1
        self._total_pages = 1
        self._worker: ApiWorker | None = None

        self._build_ui()
        self._load_users()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(QLabel("Usuários", objectName="PageTitle"))
        header.addStretch(1)
        new_button = QPushButton("+ Novo Usuário", objectName="PrimaryButton")
        new_button.clicked.connect(self._handle_new_clicked)
        header.addWidget(new_button)
        layout.addLayout(header)

        toolbar = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Buscar por nome ou e-mail...")
        self._search_input.returnPressed.connect(self._handle_search)
        toolbar.addWidget(self._search_input, stretch=1)

        self._status_filter = QComboBox()
        for label, _value in _STATUS_FILTER_OPTIONS:
            self._status_filter.addItem(label)
        self._status_filter.currentIndexChanged.connect(self._handle_search)
        toolbar.addWidget(self._status_filter)

        search_button = QPushButton("Buscar", objectName="LinkButton")
        search_button.clicked.connect(self._handle_search)
        toolbar.addWidget(search_button)
        layout.addLayout(toolbar)

        self._status_message = QLabel("")
        self._status_message.setObjectName("Muted")
        self._status_message.hide()
        layout.addWidget(self._status_message)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Nome", "E-mail", "Papel", "Status", ""])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(2, 130)
        self._table.setColumnWidth(3, 100)
        self._table.setColumnWidth(4, 170)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(44)
        apply_shadow(self._table, blur=20, y_offset=4, alpha=15)
        layout.addWidget(self._table, stretch=1)

        pagination = QHBoxLayout()
        self._page_label = QLabel("")
        self._page_label.setObjectName("Muted")
        pagination.addWidget(self._page_label)
        pagination.addStretch(1)
        self._prev_button = QPushButton("‹ Anterior", objectName="LinkButton")
        self._prev_button.clicked.connect(self._go_previous_page)
        self._next_button = QPushButton("Próxima ›", objectName="LinkButton")
        self._next_button.clicked.connect(self._go_next_page)
        pagination.addWidget(self._prev_button)
        pagination.addWidget(self._next_button)
        layout.addLayout(pagination)

    def _handle_search(self) -> None:
        self._page = 1
        self._load_users()

    def _go_previous_page(self) -> None:
        if self._page > 1:
            self._page -= 1
            self._load_users()

    def _go_next_page(self) -> None:
        if self._page < self._total_pages:
            self._page += 1
            self._load_users()

    def _load_users(self) -> None:
        status_value = _STATUS_FILTER_OPTIONS[self._status_filter.currentIndex()][1]
        self._worker = ApiWorker(
            self._api_client.list_users, self._session.access_token,
            q=self._search_input.text().strip() or None, status=status_value, page=self._page, page_size=_PAGE_SIZE,
        )
        self._worker.succeeded.connect(self._handle_users_loaded)
        self._worker.failed.connect(self._handle_load_failed)
        self._worker.start()

    def _handle_users_loaded(self, result: dict) -> None:
        items = result["items"]
        meta = result["meta"]
        self._total_pages = meta["total_pages"]
        self._page = meta["page"]

        self._table.setRowCount(0)
        for row, user in enumerate(items):
            self._table.insertRow(row)
            name_item = QTableWidgetItem(user["full_name"])
            name_font = name_item.font()
            name_font.setBold(True)
            name_item.setFont(name_font)
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, QTableWidgetItem(user["email"]))
            self._table.setItem(row, 2, QTableWidgetItem(_ROLE_LABELS.get(user["role_code"], user["role_code"])))
            text, badge_class = _STATUS_DISPLAY.get(user["status"], (user["status"], "BadgeNeutral"))
            self._table.setCellWidget(row, 3, build_badge(text, badge_class))
            self._table.setCellWidget(row, 4, self._build_row_actions(user))

        self._page_label.setText(f"Página {meta['page']} de {meta['total_pages']} — {meta['total']} usuário(s)")
        self._prev_button.setEnabled(self._page > 1)
        self._next_button.setEnabled(self._page < self._total_pages)

    def _handle_load_failed(self, exc: Exception) -> None:
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível carregar os usuários."
        self._show_status(message, is_error=True)

    def _build_row_actions(self, user: dict) -> QWidget:
        container = QWidget()
        row_layout = QHBoxLayout(container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        edit_button = QPushButton("Editar", objectName="LinkButton")
        edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_button.clicked.connect(lambda: self._handle_edit_clicked(user))
        row_layout.addWidget(edit_button)

        is_self = user["id"] == self._session.user_id
        if not is_self:
            if user["status"] == "ATIVO":
                toggle_button = QPushButton("Desativar", objectName="DangerLinkButton")
                toggle_button.clicked.connect(lambda: self._handle_toggle_status(user, "INATIVO"))
            else:
                toggle_button = QPushButton("Ativar", objectName="LinkButton")
                toggle_button.clicked.connect(lambda: self._handle_toggle_status(user, "ATIVO"))
            toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
            row_layout.addWidget(toggle_button)

        row_layout.addStretch(1)
        return container

    def _handle_new_clicked(self) -> None:
        dialog = UserDialog(self._api_client, self._session.access_token)
        if dialog.exec():
            self._show_status(f"Usuário {dialog.saved_user['full_name']} criado com sucesso.")
            self._load_users()

    def _handle_edit_clicked(self, user: dict) -> None:
        dialog = UserDialog(self._api_client, self._session.access_token, user=user)
        if dialog.exec():
            self._show_status(f"Usuário {dialog.saved_user['full_name']} atualizado com sucesso.")
            self._load_users()

    def _handle_toggle_status(self, user: dict, new_status: str) -> None:
        if new_status == "INATIVO":
            confirmation = QMessageBox.question(
                self, "Desativar usuário",
                f"Tem certeza que deseja desativar {user['full_name']}?\n\nEla(e) não conseguirá mais acessar o sistema.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirmation != QMessageBox.StandardButton.Yes:
                return
        worker = ApiWorker(self._api_client.update_user, self._session.access_token, user["id"], {"status": new_status})
        worker.succeeded.connect(lambda _r: self._handle_toggle_succeeded(user["full_name"], new_status))
        worker.failed.connect(self._handle_load_failed)
        worker.start()
        self._toggle_worker = worker

    def _handle_toggle_succeeded(self, name: str, new_status: str) -> None:
        verb = "reativado" if new_status == "ATIVO" else "desativado"
        self._show_status(f"Usuário {name} {verb}.")
        self._load_users()

    def _show_status(self, message: str, *, is_error: bool = False) -> None:
        self._status_message.setObjectName("ErrorBanner" if is_error else "Muted")
        self._status_message.style().unpolish(self._status_message)
        self._status_message.style().polish(self._status_message)
        self._status_message.setText(message)
        self._status_message.show()
        if not is_error:
            QTimer.singleShot(4000, self._status_message.hide)
