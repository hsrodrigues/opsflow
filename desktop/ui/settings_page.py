"""Settings screen (seção 26, "Configurações") — auto-atendimento: qualquer
usuário logado edita o próprio nome/telefone (`PATCH /api/v1/auth/me`), sem
depender da permissão `users.manage` que só admins têm (essa segue exclusiva
da tela Usuários, e só pra editar OUTRAS pessoas). Não tem campo de senha de
propósito: nunca existiu um fluxo de "esqueci minha senha" self-service
nesse produto, e a decisão foi não criar um — trocar a própria senha (ou a
de qualquer outro usuário) é sempre uma ação do admin da empresa, editando o
usuário na tela Usuários.
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import DesktopConfig
from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.theme import apply_shadow
from ui.widgets import build_badge
from utils.masks import bind_live_format, format_phone

_ROLE_LABELS = {
    "SUPER_ADMIN": "Administrador da Plataforma", "ADMIN_EMPRESA": "Administrador",
    "SUPERVISOR": "Supervisor", "OPERADOR": "Operador", "VISUALIZADOR": "Visualizador",
}


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _build_profile_row(label_text: str, field: QWidget) -> QWidget:
    """Uma linha "rótulo à esquerda + campo à direita" — feita à mão, uma
    por linha, em vez de um único `QFormLayout.addRow(...)` pra cada campo.
    Ver `SettingsPage.showEvent`/`_force_relayout` pro motivo real: esta
    página some numa `QStackedWidget` sem nenhum evento de tela entre ser
    construída e virar a atual, e sem forçar um resize de verdade da janela
    depois disso, um bloco de linhas aninhado (`QFormLayout` OU uma
    `QVBoxLayout` extra agrupando estas linhas — ambos testados) sai com
    geometria errada na primeira pintura. Este jeito mais raso (cada linha
    direto no layout do card, sem uma camada extra de agrupamento) reduz o
    quanto isso aparece, mas quem realmente resolve é o resize forçado."""
    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(12)
    label = QLabel(label_text)
    label.setFixedWidth(140)
    row_layout.addWidget(label)
    row_layout.addWidget(field, stretch=1)
    return row


class SettingsPage(QWidget):
    def __init__(self, config: DesktopConfig, api_client: ApiClient, session: UserSession) -> None:
        super().__init__()
        self._config = config
        self._api_client = api_client
        self._session = session
        self._worker: ApiWorker | None = None

        self._build_ui()
        self._load_current_values()
        self._load_connection_status()
        if self._panel_card is not None:
            self._load_panel_token()

    def showEvent(self, event) -> None:  # noqa: N802 - nome do Qt
        """A primeira vez que esta página vira a atual do `QStackedWidget`
        (a troca acontece no mesmo evento que a constrói — `MainWindow.
        _navigate_to` faz `factory(self)` seguido de `setCurrentIndex` sem
        nenhum evento de tela no meio), os cartões desta página saem com
        linhas sobrepostas/cortadas: só um resize de verdade da JANELA DE
        TOPO (não desta página — a geometria dela é gerenciada pelo
        `QStackedWidget`, que sobrescreve `self.resize()` de volta na hora)
        faz o Qt recalcular a geometria direito. Bug real, reproduzido de
        forma 100% determinística (não é frescura de timing) — sem isto o
        usuário via a mensagem "tudo colado" reportada nesta mesma tela."""
        super().showEvent(event)
        QTimer.singleShot(0, self._force_relayout)

    def _force_relayout(self) -> None:
        top = self.window()
        size = top.size()
        top.resize(size.width() + 1, size.height())
        top.resize(size)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        layout.addWidget(QLabel("Configurações", objectName="PageTitle"))
        layout.addWidget(QLabel("Suas informações de conta neste sistema", objectName="Muted"))

        self._status_message = QLabel("")
        self._status_message.setObjectName("Muted")
        self._status_message.hide()
        layout.addWidget(self._status_message)

        # --- cartão "Meu perfil" ---
        profile_card = QFrame(objectName="Card")
        # Largura máxima: sem isto o card estica até a borda da janela (que é
        # bem larga nas outras telas, cheias de tabela) e o botão abaixo vira
        # uma barra enorme de ponta a ponta. Um formulário de perfil lê
        # melhor numa coluna estreita, como em qualquer tela de conta.
        profile_card.setMaximumWidth(640)
        apply_shadow(profile_card, blur=20, y_offset=6, alpha=16)
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.setContentsMargins(20, 18, 20, 18)
        profile_layout.setSpacing(14)

        header_row = QVBoxLayout()
        header_row.setSpacing(2)
        header_row.addWidget(QLabel("Meu perfil", objectName="SectionTitle"))
        header_row.addWidget(
            QLabel("Essas informações aparecem para o resto da sua equipe.", objectName="Muted")
        )
        profile_layout.addLayout(header_row)

        # Cada linha vai direto no `profile_layout` (sem uma `rows_layout`
        # intermediária) — um nível a menos de aninhamento entre o card e o
        # campo de verdade, o suficiente pra deixar de precisar de um
        # segundo resize pra convergir a largura na primeira exibição.
        self._email_value = QLabel("—", objectName="Muted")
        profile_layout.addWidget(_build_profile_row("E-mail", self._email_value))
        profile_layout.addWidget(_build_profile_row("Papel", self._build_role_badge_holder()))

        self._full_name_input = QLineEdit()
        self._full_name_input.setPlaceholderText("Seu nome completo")
        profile_layout.addWidget(_build_profile_row("Nome completo *", self._full_name_input))

        self._phone_input = QLineEdit()
        self._phone_input.setPlaceholderText("(00) 00000-0000")
        self._phone_input.setMaxLength(15)
        bind_live_format(self._phone_input, format_phone)
        profile_layout.addWidget(_build_profile_row("Telefone", self._phone_input))

        save_row = QHBoxLayout()
        self._save_button = QPushButton("Salvar alterações", objectName="PrimaryButton")
        self._save_button.clicked.connect(self._handle_save_clicked)
        save_row.addWidget(self._save_button)
        save_row.addStretch(1)
        profile_layout.addLayout(save_row)

        layout.addWidget(profile_card)

        # --- cartão "Senha" — sem campo de senha nenhum, de propósito ---
        password_card = QFrame(objectName="Card")
        password_card.setMaximumWidth(640)  # antes do conteúdo — ver comentário no profile_card
        apply_shadow(password_card, blur=20, y_offset=6, alpha=16)
        password_layout = QVBoxLayout(password_card)
        password_layout.setContentsMargins(20, 18, 20, 18)
        password_layout.setSpacing(4)
        password_layout.addWidget(QLabel("Senha de acesso", objectName="SectionTitle"))
        note = QLabel(
            "Por segurança, a troca de senha é feita pelo administrador da sua empresa, "
            "editando o seu usuário na tela Usuários — não existe um fluxo de \"esqueci "
            "minha senha\" pelo próprio login. Se você esqueceu a sua, peça para o "
            "administrador definir uma nova."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        password_layout.addWidget(note)
        layout.addWidget(password_card)

        # --- cartão "Painel de operações (TV)" — só pra quem administra a
        # empresa; ideia do usuário: uma tela pública somente-leitura pra
        # deixar numa TV do centro de operações, mostrando de onde pra onde
        # cada carga vai e o status ao vivo, sem depender de rastreador. ---
        self._panel_card: QFrame | None = None
        if "ADMIN_EMPRESA" in self._session.roles:
            panel_card = QFrame(objectName="Card")
            panel_card.setMaximumWidth(640)  # antes do conteúdo — ver comentário no profile_card
            apply_shadow(panel_card, blur=20, y_offset=6, alpha=16)
            panel_layout = QVBoxLayout(panel_card)
            panel_layout.setContentsMargins(20, 18, 20, 18)
            panel_layout.setSpacing(10)
            panel_layout.addWidget(QLabel("Painel de operações (TV)", objectName="SectionTitle"))
            panel_subtitle = QLabel(
                "Um link somente-leitura para deixar aberto numa TV do centro de operações — "
                "mostra o mapa e o status de cada carga em tempo real, sem precisar fazer login.",
                objectName="Muted",
            )
            panel_subtitle.setWordWrap(True)
            panel_layout.addWidget(panel_subtitle)

            link_row = QHBoxLayout()
            self._panel_link_input = QLineEdit()
            self._panel_link_input.setReadOnly(True)
            self._panel_link_input.setPlaceholderText("Gerando link...")
            link_row.addWidget(self._panel_link_input, stretch=1)
            copy_button = QPushButton("Copiar link", objectName="SecondaryButton")
            copy_button.clicked.connect(self._handle_copy_panel_link)
            link_row.addWidget(copy_button)
            panel_layout.addLayout(link_row)

            regenerate_row = QHBoxLayout()
            regenerate_button = QPushButton("Gerar novo link", objectName="SecondaryButton")
            regenerate_button.clicked.connect(self._handle_regenerate_panel_link)
            regenerate_row.addWidget(regenerate_button)
            regenerate_row.addStretch(1)
            panel_layout.addLayout(regenerate_row)
            panel_hint = QLabel(
                "Gerar um novo link desativa o anterior — quem tiver o link antigo aberto na TV "
                "para de ver atualizações.", objectName="Faint",
            )
            panel_hint.setWordWrap(True)
            panel_layout.addWidget(panel_hint)

            layout.addWidget(panel_card)
            self._panel_card = panel_card

        # --- cartão "Sobre" ---
        about_card = QFrame(objectName="Card")
        about_card.setMaximumWidth(640)  # antes do conteúdo — ver comentário no profile_card
        apply_shadow(about_card, blur=20, y_offset=6, alpha=16)
        about_layout = QFormLayout(about_card)
        about_layout.setContentsMargins(20, 18, 20, 18)
        about_layout.setSpacing(8)
        about_layout.addRow(QLabel("Sobre o sistema", objectName="SectionTitle"))
        about_layout.addRow("Versão", QLabel(self._config.app_version, objectName="Muted"))
        about_layout.addRow("Servidor", QLabel(self._config.api_base_url, objectName="Muted"))
        self._database_value = QLabel("Consultando...", objectName="Muted")
        about_layout.addRow("Banco de dados", self._database_value)
        connection_holder = QWidget()
        self._connection_status_slot = QVBoxLayout(connection_holder)
        self._connection_status_slot.setContentsMargins(0, 0, 0, 0)
        about_layout.addRow("Status da conexão", connection_holder)
        layout.addWidget(about_card)

        layout.addStretch(1)

    def _build_role_badge_holder(self) -> QWidget:
        holder = QWidget()
        self._role_badge_layout = QVBoxLayout(holder)
        self._role_badge_layout.setContentsMargins(0, 0, 0, 0)
        return holder

    def _load_current_values(self) -> None:
        self._email_value.setText(self._session.email or "—")
        self._full_name_input.setText(self._session.full_name or "")
        if self._session.phone:
            self._phone_input.setText(self._session.phone)

        primary_role = self._session.roles[0] if self._session.roles else None
        role_label = _ROLE_LABELS.get(primary_role, primary_role or "—")
        self._role_badge_layout.addWidget(build_badge(role_label, "BadgeNeutral"))

    def _load_connection_status(self) -> None:
        # `/api/health` não exige token — checagem simples de conectividade,
        # a mesma rota que já alimenta o indicador 🟢/🔴 do topbar (seção 32),
        # só que agora também mostrando EM QUAL banco (host) o backend está
        # falando de verdade. Pedido depois de mais de uma confusão nesta
        # sessão sobre "qual banco tá ativo agora" (local vs. nuvem).
        self._health_worker = ApiWorker(self._api_client.check_health)
        self._health_worker.succeeded.connect(self._handle_connection_status_succeeded)
        self._health_worker.failed.connect(self._handle_connection_status_failed)
        self._health_worker.start()

    def _handle_connection_status_succeeded(self, result: dict) -> None:
        self._database_value.setText(result.get("database_host") or "—")
        database_up = result.get("database") == "up"
        text = "Conectado" if database_up else "Sem conexão com o banco"
        badge_class = "BadgeSuccess" if database_up else "BadgeDanger"
        self._set_connection_badge(text, badge_class)

    def _handle_connection_status_failed(self, _exc: Exception) -> None:
        self._database_value.setText("—")
        self._set_connection_badge("Servidor inacessível", "BadgeDanger")

    def _set_connection_badge(self, text: str, badge_class: str) -> None:
        while self._connection_status_slot.count():
            item = self._connection_status_slot.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._connection_status_slot.addWidget(build_badge(text, badge_class))

    def _load_panel_token(self) -> None:
        self._panel_worker = ApiWorker(self._api_client.get_panel_token, self._session.access_token)
        self._panel_worker.succeeded.connect(self._handle_panel_token_loaded)
        self._panel_worker.failed.connect(lambda _exc: self._panel_link_input.setPlaceholderText("Indisponível"))
        self._panel_worker.start()

    def _handle_panel_token_loaded(self, result: dict) -> None:
        full_url = self._config.api_base_url.rstrip("/") + result["board_path"]
        self._panel_link_input.setText(full_url)

    def _handle_copy_panel_link(self) -> None:
        link = self._panel_link_input.text().strip()
        if not link:
            return
        QApplication.clipboard().setText(link)
        self._show_status("Link do painel copiado.")

    def _handle_regenerate_panel_link(self) -> None:
        confirm = QMessageBox.question(
            self, "Gerar novo link do painel",
            "O link atual do painel de TV vai parar de funcionar imediatamente. "
            "Qualquer tela que já esteja usando o link antigo vai precisar do novo. Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._regenerate_worker = ApiWorker(self._api_client.regenerate_panel_token, self._session.access_token)
        self._regenerate_worker.succeeded.connect(self._handle_panel_regenerated)
        self._regenerate_worker.failed.connect(
            lambda _exc: self._show_status("Não foi possível gerar um novo link.", is_error=True)
        )
        self._regenerate_worker.start()

    def _handle_panel_regenerated(self, result: dict) -> None:
        self._handle_panel_token_loaded(result)
        self._show_status("Novo link do painel gerado.")

    def _handle_save_clicked(self) -> None:
        full_name = self._full_name_input.text().strip()
        if not full_name:
            self._show_status("Informe seu nome completo.", is_error=True)
            return

        payload = {"full_name": full_name, "phone": self._phone_input.text().strip() or None}
        self._save_button.setEnabled(False)
        self._worker = ApiWorker(self._api_client.update_my_profile, self._session.access_token, payload)
        self._worker.succeeded.connect(self._handle_save_succeeded)
        self._worker.failed.connect(self._handle_save_failed)
        self._worker.start()

    def _handle_save_succeeded(self, user: dict) -> None:
        self._save_button.setEnabled(True)
        self._session.full_name = user["full_name"]
        self._session.phone = user.get("phone")
        self._show_status("Perfil atualizado com sucesso.")

    def _handle_save_failed(self, exc: Exception) -> None:
        self._save_button.setEnabled(True)
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível salvar suas alterações."
        self._show_status(message, is_error=True)

    def _show_status(self, message: str, *, is_error: bool = False) -> None:
        self._status_message.setObjectName("ErrorBanner" if is_error else "Muted")
        _repolish(self._status_message)
        self._status_message.setText(message)
        self._status_message.show()
        if not is_error:
            QTimer.singleShot(4000, self._status_message.hide)
