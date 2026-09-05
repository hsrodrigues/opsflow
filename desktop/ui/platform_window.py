"""Platform console shell (seção 54) — a janela que um `SUPER_ADMIN` vê em
vez do `MainWindow` normal: não tem sidebar de cadastros/operação (nada
disso faz sentido sem um tenant), só a lista de empresas clientes e como
gerenciar a licença de cada uma. `desktop/main.py` decide qual das duas
janelas abrir, olhando `session.tenant_id is None`.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import DesktopConfig
from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.license_key_dialog import LicenseKeyDialog
from ui.tenant_dialog import TenantDialog
from ui.tenant_license_dialog import TenantLicenseDialog
from ui.theme import apply_shadow, make_scroll_area_transparent
from ui.widgets import build_badge, build_logo_mark
from utils.formatting import format_datetime_br, format_file_size

_LICENSE_STATUS_DISPLAY = {
    "ACTIVE": ("Ativa", "BadgeSuccess"), "TRIAL": ("Em teste", "BadgeWarning"),
    "SUSPENDED": ("Suspensa", "BadgeDanger"), "EXPIRED": ("Expirada", "BadgeDanger"),
    "CANCELLED": ("Cancelada", "BadgeDanger"),
}


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class PlatformWindow(QWidget):
    def __init__(
        self, config: DesktopConfig, api_client: ApiClient, session: UserSession, on_logout, apply_theme_callback,
    ) -> None:
        super().__init__()
        self._config = config
        self._api_client = api_client
        self._session = session
        self._on_logout = on_logout
        self._apply_theme_callback = apply_theme_callback
        self._dark_mode = False
        self._worker: ApiWorker | None = None
        self._logout_worker: ApiWorker | None = None

        self.setObjectName("AppRoot")
        self.setWindowTitle("OpsFlow — Console de Plataforma")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 640)

        self._build_ui()
        self._load_tenants()
        self._load_license_keys()
        self._load_backups()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_topbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        make_scroll_area_transparent(scroll)

        content_widget = QWidget()
        content = QVBoxLayout(content_widget)
        content.setContentsMargins(24, 20, 24, 20)
        content.setSpacing(12)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.addWidget(QLabel("Empresas clientes", objectName="PageTitle"))
        title_col.addWidget(QLabel("Console de plataforma — gestão de tenants e licenças", objectName="Muted"))
        header.addLayout(title_col)
        header.addStretch(1)
        new_button = QPushButton("+ Nova Empresa", objectName="PrimaryButton")
        new_button.clicked.connect(self._handle_new_clicked)
        header.addWidget(new_button)
        content.addLayout(header)

        self._status_message = QLabel("")
        self._status_message.setObjectName("Muted")
        self._status_message.hide()
        content.addWidget(self._status_message)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Empresa", "Plano", "Licença", "Usuários", "Veículos", "Situação", ""]
        )
        header_view = self._table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            header_view.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 110)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(3, 90)
        self._table.setColumnWidth(4, 90)
        self._table.setColumnWidth(5, 100)
        self._table.setColumnWidth(6, 220)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(44)
        self._table.setMinimumHeight(260)
        apply_shadow(self._table, blur=20, y_offset=4, alpha=15)
        content.addWidget(self._table)

        content.addSpacing(28)
        content.addLayout(self._build_license_keys_header())

        self._keys_status_message = QLabel("")
        self._keys_status_message.setObjectName("Muted")
        self._keys_status_message.hide()
        content.addWidget(self._keys_status_message)

        self._keys_table = QTableWidget(0, 6)
        self._keys_table.setHorizontalHeaderLabels(
            ["Chave", "Plano", "Gerada em", "Teste (dias)", "Situação", "Empresa"]
        )
        keys_header_view = self._keys_table.horizontalHeader()
        keys_header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            keys_header_view.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        keys_header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        keys_header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._keys_table.setColumnWidth(1, 120)
        self._keys_table.setColumnWidth(2, 150)
        self._keys_table.setColumnWidth(3, 100)
        self._keys_table.setColumnWidth(4, 170)
        self._keys_table.verticalHeader().setVisible(False)
        self._keys_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._keys_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._keys_table.setAlternatingRowColors(True)
        self._keys_table.setShowGrid(False)
        self._keys_table.verticalHeader().setDefaultSectionSize(44)
        self._keys_table.setMinimumHeight(220)
        apply_shadow(self._keys_table, blur=20, y_offset=4, alpha=15)
        content.addWidget(self._keys_table)

        content.addSpacing(28)
        content.addLayout(self._build_backups_header())

        self._backups_status_message = QLabel("")
        self._backups_status_message.setObjectName("Muted")
        self._backups_status_message.hide()
        content.addWidget(self._backups_status_message)

        self._backups_table = QTableWidget(0, 4)
        self._backups_table.setHorizontalHeaderLabels(["Arquivo", "Criado em", "Tamanho", ""])
        backups_header_view = self._backups_table.horizontalHeader()
        backups_header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            backups_header_view.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        self._backups_table.setColumnWidth(1, 160)
        self._backups_table.setColumnWidth(2, 100)
        self._backups_table.setColumnWidth(3, 140)
        self._backups_table.verticalHeader().setVisible(False)
        self._backups_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._backups_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._backups_table.setAlternatingRowColors(True)
        self._backups_table.setShowGrid(False)
        self._backups_table.verticalHeader().setDefaultSectionSize(44)
        self._backups_table.setMinimumHeight(180)
        apply_shadow(self._backups_table, blur=20, y_offset=4, alpha=15)
        content.addWidget(self._backups_table)

        scroll.setWidget(content_widget)
        outer.addWidget(scroll, stretch=1)

    def _build_backups_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.addWidget(QLabel("Backups", objectName="PageTitle"))
        title_col.addWidget(
            QLabel(
                "Backup automático diário do banco inteiro, com histórico pra restaurar",
                objectName="Muted",
            )
        )
        header.addLayout(title_col)
        header.addStretch(1)
        self._archive_button = QPushButton("Arquivar dados antigos", objectName="SecondaryButton")
        self._archive_button.clicked.connect(self._handle_archive_clicked)
        header.addWidget(self._archive_button)
        self._backup_now_button = QPushButton("Fazer backup agora", objectName="SecondaryButton")
        self._backup_now_button.clicked.connect(self._handle_backup_now_clicked)
        header.addWidget(self._backup_now_button)
        return header

    def _build_license_keys_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.addWidget(QLabel("Chaves de ativação", objectName="PageTitle"))
        title_col.addWidget(
            QLabel("Gere uma chave sem empresa vinculada — o cliente ativa sozinho", objectName="Muted")
        )
        header.addLayout(title_col)
        header.addStretch(1)
        generate_button = QPushButton("+ Gerar chave", objectName="SecondaryButton")
        generate_button.clicked.connect(self._handle_generate_key_clicked)
        header.addWidget(generate_button)
        return header

    def _build_topbar(self) -> QWidget:
        topbar = QWidget(objectName="Topbar")
        topbar.setFixedHeight(60)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(24, 0, 20, 0)

        layout.addWidget(build_logo_mark(30))
        layout.addSpacing(10)
        layout.addWidget(QLabel("OPSFLOW · PLATAFORMA", objectName="SidebarSection"))
        layout.addStretch(1)

        theme_button = QPushButton("🌙", objectName="IconButton")
        theme_button.setToolTip("Alternar tema claro/escuro")
        theme_button.setFixedSize(32, 32)
        theme_button.clicked.connect(self._toggle_theme)
        layout.addWidget(theme_button)
        layout.addSpacing(18)

        user_label = QLabel(self._session.full_name or self._session.email or "")
        layout.addWidget(user_label)
        layout.addSpacing(12)

        logout_button = QPushButton("Sair", objectName="LinkButton")
        logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_button.clicked.connect(self._handle_logout_clicked)
        layout.addWidget(logout_button)

        return topbar

    # --- dados ---

    def _load_tenants(self) -> None:
        self._worker = ApiWorker(self._api_client.list_tenants, self._session.access_token)
        self._worker.succeeded.connect(self._apply_tenants)
        self._worker.failed.connect(self._handle_load_failed)
        self._worker.start()

    def _apply_tenants(self, tenants: list) -> None:
        self._table.setRowCount(0)
        for row, tenant in enumerate(tenants):
            self._table.insertRow(row)
            name_item = QTableWidgetItem(tenant["legal_name"])
            name_font = name_item.font()
            name_font.setBold(True)
            name_item.setFont(name_font)
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, QTableWidgetItem(tenant.get("plan_code") or "—"))
            text, badge_class = _LICENSE_STATUS_DISPLAY.get(
                tenant.get("license_status"), (tenant.get("license_status") or "—", "BadgeNeutral"),
            )
            self._table.setCellWidget(row, 2, build_badge(text, badge_class))
            max_users = tenant.get("max_users")
            self._table.setItem(row, 3, QTableWidgetItem(f"{tenant['user_count']} / {max_users if max_users else '∞'}"))
            max_vehicles = tenant.get("max_vehicles")
            self._table.setItem(
                row, 4, QTableWidgetItem(f"{tenant['vehicle_count']} / {max_vehicles if max_vehicles else '∞'}")
            )
            situacao_text, situacao_class = ("Ativa", "BadgeSuccess") if tenant["is_active"] else ("Inativa", "BadgeNeutral")
            self._table.setCellWidget(row, 5, build_badge(situacao_text, situacao_class))
            self._table.setCellWidget(row, 6, self._build_row_actions(tenant))

        self._page_label_text = f"{len(tenants)} empresa(s) cadastrada(s)."

    def _handle_load_failed(self, exc: Exception) -> None:
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível carregar as empresas."
        self._show_status(message, is_error=True)

    def _load_license_keys(self) -> None:
        self._keys_worker = ApiWorker(self._api_client.list_license_keys, self._session.access_token)
        self._keys_worker.succeeded.connect(self._apply_license_keys)
        self._keys_worker.failed.connect(self._handle_load_keys_failed)
        self._keys_worker.start()

    def _apply_license_keys(self, keys: list) -> None:
        self._keys_table.setRowCount(0)
        for row, key in enumerate(keys):
            self._keys_table.insertRow(row)
            key_item = QTableWidgetItem(key["license_key"])
            key_font = key_item.font()
            key_font.setBold(True)
            key_item.setFont(key_font)
            self._keys_table.setItem(row, 0, key_item)
            self._keys_table.setItem(row, 1, QTableWidgetItem(key.get("plan_code") or "—"))
            self._keys_table.setItem(row, 2, QTableWidgetItem(format_datetime_br(key["issued_at"])))
            trial_days = key.get("pending_trial_days")
            self._keys_table.setItem(row, 3, QTableWidgetItem(str(trial_days) if trial_days else "—"))
            if key.get("tenant_id"):
                situacao_text, situacao_class = "Ativada", "BadgeSuccess"
            else:
                situacao_text, situacao_class = "Aguardando ativação", "BadgeWarning"
            self._keys_table.setCellWidget(row, 4, build_badge(situacao_text, situacao_class))
            self._keys_table.setItem(row, 5, QTableWidgetItem(key.get("tenant_name") or "—"))

    def _handle_load_keys_failed(self, exc: Exception) -> None:
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível carregar as chaves."
        self._show_keys_status(message, is_error=True)

    def _handle_generate_key_clicked(self) -> None:
        dialog = LicenseKeyDialog(self._api_client, self._session.access_token)
        if dialog.exec():
            self._show_keys_status("Chave de ativação gerada com sucesso.")
            self._load_license_keys()

    def _show_keys_status(self, message: str, *, is_error: bool = False) -> None:
        self._keys_status_message.setObjectName("ErrorBanner" if is_error else "Muted")
        _repolish(self._keys_status_message)
        self._keys_status_message.setText(message)
        self._keys_status_message.show()
        if not is_error:
            QTimer.singleShot(4000, self._keys_status_message.hide)

    def _load_backups(self) -> None:
        self._backups_worker = ApiWorker(self._api_client.list_backups, self._session.access_token)
        self._backups_worker.succeeded.connect(self._apply_backups)
        self._backups_worker.failed.connect(self._handle_load_backups_failed)
        self._backups_worker.start()

    def _apply_backups(self, backups: list) -> None:
        self._backups_table.setRowCount(0)
        for row, backup in enumerate(backups):
            self._backups_table.insertRow(row)
            name_item = QTableWidgetItem(backup["filename"])
            name_font = name_item.font()
            name_font.setBold(True)
            name_item.setFont(name_font)
            self._backups_table.setItem(row, 0, name_item)
            self._backups_table.setItem(row, 1, QTableWidgetItem(format_datetime_br(backup["created_at"])))
            self._backups_table.setItem(row, 2, QTableWidgetItem(format_file_size(backup["size_bytes"])))

            restore_button = QPushButton("Restaurar", objectName="DangerLinkButton")
            restore_button.setCursor(Qt.CursorShape.PointingHandCursor)
            restore_button.clicked.connect(lambda _checked=False, b=backup: self._handle_restore_clicked(b))
            self._backups_table.setCellWidget(row, 3, restore_button)

        if not backups:
            self._show_backups_status("Nenhum backup ainda — clique em \"Fazer backup agora\".")

    def _handle_load_backups_failed(self, exc: Exception) -> None:
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível carregar os backups."
        self._show_backups_status(message, is_error=True)

    def _handle_archive_clicked(self) -> None:
        months, confirmed = QInputDialog.getInt(
            self, "Arquivar dados antigos",
            "Arquivar operações e ocorrências já concluídas/canceladas há mais de quantos meses?\n"
            "(elas saem das tabelas principais — de todas as empresas — e vão pra tabelas de arquivo)",
            12, 1, 120,
        )
        if not confirmed:
            return
        confirmation = QMessageBox.question(
            self, "Confirmar arquivamento",
            f"Arquivar tudo com mais de {months} mês(es), de TODAS as empresas clientes?\n\n"
            "Os dados saem das tabelas principais (não são apagados, ficam em tabelas de arquivo).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        self._archive_button.setEnabled(False)
        worker = ApiWorker(self._api_client.archive_old_records, self._session.access_token, months)
        worker.succeeded.connect(self._handle_archive_succeeded)
        worker.failed.connect(self._handle_archive_failed)
        worker.start()
        self._archive_worker = worker

    def _handle_archive_succeeded(self, result: dict) -> None:
        self._archive_button.setEnabled(True)
        self._show_backups_status(
            f"Arquivamento concluído: {result['operations_archived']} operação(ões) e "
            f"{result['occurrences_archived']} ocorrência(s)."
        )

    def _handle_archive_failed(self, exc: Exception) -> None:
        self._archive_button.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível arquivar os dados."
        self._show_backups_status(message, is_error=True)

    def _handle_backup_now_clicked(self) -> None:
        self._backup_now_button.setEnabled(False)
        self._backup_now_button.setText("Gerando backup...")
        worker = ApiWorker(self._api_client.create_backup, self._session.access_token)
        worker.succeeded.connect(self._handle_backup_now_succeeded)
        worker.failed.connect(self._handle_backup_now_failed)
        worker.start()
        self._backup_now_worker = worker

    def _handle_backup_now_succeeded(self, backup: dict) -> None:
        self._backup_now_button.setEnabled(True)
        self._backup_now_button.setText("Fazer backup agora")
        self._show_backups_status(f"Backup {backup['filename']} criado com sucesso.")
        self._load_backups()

    def _handle_backup_now_failed(self, exc: Exception) -> None:
        self._backup_now_button.setEnabled(True)
        self._backup_now_button.setText("Fazer backup agora")
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível gerar o backup."
        self._show_backups_status(message, is_error=True)

    def _handle_restore_clicked(self, backup: dict) -> None:
        # Restaurar SOBRESCREVE o banco inteiro com o estado daquele momento
        # — de todas as empresas, não só de uma. Confirmação forte de
        # propósito: pedir pra digitar a palavra "RESTAURAR" em vez de só
        # Sim/Não, porque um clique duplo acidental num botão "Sim" é fácil
        # demais pra uma ação desse tamanho.
        confirmation = QMessageBox(self)
        confirmation.setIcon(QMessageBox.Icon.Warning)
        confirmation.setWindowTitle("Restaurar backup")
        confirmation.setText(f"Restaurar {backup['filename']}?")
        confirmation.setInformativeText(
            "Isso SUBSTITUI o banco de dados inteiro — de TODAS as empresas clientes — pelo "
            f"estado salvo em {format_datetime_br(backup['created_at'])}. Qualquer dado criado "
            "depois desse momento será perdido. Esta ação não pode ser desfeita."
        )
        confirmation.setStandardButtons(QMessageBox.StandardButton.Cancel)
        proceed_button = confirmation.addButton("Restaurar mesmo assim", QMessageBox.ButtonRole.DestructiveRole)
        confirmation.exec()
        if confirmation.clickedButton() is not proceed_button:
            return

        worker = ApiWorker(self._api_client.restore_backup, self._session.access_token, backup["filename"])
        worker.succeeded.connect(lambda _r: self._handle_restore_succeeded(backup["filename"]))
        worker.failed.connect(self._handle_restore_failed)
        worker.start()
        self._restore_worker = worker
        self._show_backups_status(f"Restaurando {backup['filename']}...")

    def _handle_restore_succeeded(self, filename: str) -> None:
        self._show_backups_status(f"Banco restaurado a partir de {filename}.")
        self._load_tenants()
        self._load_license_keys()
        self._load_backups()

    def _handle_restore_failed(self, exc: Exception) -> None:
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível restaurar o backup."
        self._show_backups_status(message, is_error=True)

    def _show_backups_status(self, message: str, *, is_error: bool = False) -> None:
        self._backups_status_message.setObjectName("ErrorBanner" if is_error else "Muted")
        _repolish(self._backups_status_message)
        self._backups_status_message.setText(message)
        self._backups_status_message.show()
        if not is_error:
            QTimer.singleShot(4000, self._backups_status_message.hide)

    def _build_row_actions(self, tenant: dict) -> QWidget:
        container = QWidget()
        row_layout = QHBoxLayout(container)
        row_layout.setContentsMargins(0, 0, 0, 0)
        license_button = QPushButton("Licença", objectName="LinkButton")
        license_button.setCursor(Qt.CursorShape.PointingHandCursor)
        license_button.clicked.connect(lambda: self._handle_license_clicked(tenant))
        row_layout.addWidget(license_button)

        if tenant["is_active"]:
            toggle_button = QPushButton("Desativar", objectName="DangerLinkButton")
            toggle_button.clicked.connect(lambda: self._handle_toggle_active(tenant, False))
        else:
            toggle_button = QPushButton("Ativar", objectName="LinkButton")
            toggle_button.clicked.connect(lambda: self._handle_toggle_active(tenant, True))
        toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        row_layout.addWidget(toggle_button)
        row_layout.addStretch(1)
        return container

    # --- ações ---

    def _handle_new_clicked(self) -> None:
        dialog = TenantDialog(self._api_client, self._session.access_token)
        if dialog.exec():
            self._show_status(f"Empresa {dialog.saved_tenant['legal_name']} criada com sucesso.")
            self._load_tenants()

    def _handle_license_clicked(self, tenant: dict) -> None:
        dialog = TenantLicenseDialog(self._api_client, self._session.access_token, tenant)
        if dialog.exec():
            self._show_status(f"Licença de {tenant['legal_name']} atualizada.")
            self._load_tenants()

    def _handle_toggle_active(self, tenant: dict, activate: bool) -> None:
        if not activate:
            confirmation = QMessageBox.question(
                self, "Desativar empresa",
                f"Tem certeza que deseja desativar {tenant['legal_name']}?\n\n"
                "Os usuários dessa empresa não conseguirão mais logar.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirmation != QMessageBox.StandardButton.Yes:
                return
        worker = ApiWorker(
            self._api_client.update_tenant, self._session.access_token, tenant["id"], {"is_active": activate},
        )
        worker.succeeded.connect(lambda _r: self._handle_toggle_succeeded(tenant["legal_name"], activate))
        worker.failed.connect(self._handle_load_failed)
        worker.start()
        self._toggle_worker = worker

    def _handle_toggle_succeeded(self, name: str, activated: bool) -> None:
        verb = "reativada" if activated else "desativada"
        self._show_status(f"Empresa {name} {verb}.")
        self._load_tenants()

    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        self._apply_theme_callback(dark=self._dark_mode)

    def _handle_logout_clicked(self) -> None:
        if not self._session.refresh_token:
            self._on_logout()
            return
        self._logout_worker = ApiWorker(self._api_client.logout, self._session.refresh_token)
        self._logout_worker.succeeded.connect(lambda _result: self._on_logout())
        self._logout_worker.failed.connect(lambda _exc: self._on_logout())
        self._logout_worker.start()

    def _show_status(self, message: str, *, is_error: bool = False) -> None:
        self._status_message.setObjectName("ErrorBanner" if is_error else "Muted")
        _repolish(self._status_message)
        self._status_message.setText(message)
        self._status_message.show()
        if not is_error:
            QTimer.singleShot(4000, self._status_message.hide)
