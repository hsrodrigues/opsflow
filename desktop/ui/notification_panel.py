"""Notification bell + dropdown panel (seção 20) — the visible face of the
background robôs (`app/jobs/`): detecção de atraso, alerta de CNH e o
bloqueio automático de veículo após acidente (`occurrence_service.py`) all
write rows into `notifications`, and until this panel existed there was
nowhere in the desktop app that ever showed them — they were firing
correctly on the server with no visible proof in the client.
"""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker
from ui.theme import DARK, LIGHT, apply_shadow
from ui.widgets import build_badge

_SEVERITY_BADGE = {"WARNING": ("Alerta", "BadgeWarning"), "CRITICAL": ("Crítico", "BadgeDanger")}


def _relative_time(iso_timestamp: str) -> str:
    from datetime import datetime, timezone

    try:
        when = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return ""
    # A API grava timestamps naive em UTC (mesma convenção de `operations_page.py`
    # `_utc_now()`) — comparar um datetime "aware" com um "naive" levanta
    # TypeError, então o lado "agora" precisa espelhar o mesmo formato do `when`.
    now = datetime.now(timezone.utc) if when.tzinfo else datetime.utcnow()
    minutes = int((now - when).total_seconds() // 60)
    if minutes < 1:
        return "agora"
    if minutes < 60:
        return f"há {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"há {hours}h"
    return f"há {hours // 24}d"


class NotificationBell(QWidget):
    """Sino no topbar (seção 26) + badge de não lidas; abre `_NotificationPanel`
    ao clicar. Faz polling periódico (mesma cadência do indicador de conexão)
    para o contador de não lidas ficar atualizado sem exigir que o usuário
    abra o painel."""

    def __init__(self, api_client: ApiClient, session: UserSession) -> None:
        super().__init__()
        self._api_client = api_client
        self._session = session
        self._panel: "_NotificationPanel | None" = None
        self._worker: ApiWorker | None = None
        self._dark_mode = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._button = QPushButton("🔔", objectName="IconButton")
        self._button.setFixedSize(32, 32)
        self._button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._button.setToolTip("Notificações")
        self._button.clicked.connect(self._toggle_panel)
        layout.addWidget(self._button)

        self._badge = QLabel("", objectName="BadgeDanger")
        self._badge.setProperty("badge", "true")
        self._badge.hide()
        layout.addWidget(self._badge)

    def refresh_count(self) -> None:
        self._worker = ApiWorker(
            self._api_client.list_notifications, self._session.access_token, unread_only=True, page_size=1,
        )
        self._worker.succeeded.connect(self._apply_count)
        self._worker.failed.connect(lambda _exc: None)
        self._worker.start()

    def _apply_count(self, result: dict) -> None:
        total = result.get("meta", {}).get("total", 0)
        if total:
            self._badge.setText(str(total) if total <= 99 else "99+")
            self._badge.show()
        else:
            self._badge.hide()

    def _toggle_panel(self) -> None:
        if self._panel is not None:
            self._panel.close()
            return
        self._panel = _NotificationPanel(
            self._api_client, self._session, dark=self._dark_mode, on_closed=self._handle_panel_closed,
        )
        anchor = self._button.mapToGlobal(QPoint(0, self._button.height() + 6))
        self._panel.move(anchor.x() - self._panel.sizeHint().width() + self._button.width(), anchor.y())
        self._panel.show()
        self._panel.refresh()

    def _handle_panel_closed(self) -> None:
        self._panel = None
        self.refresh_count()

    def apply_theme(self, *, dark: bool) -> None:
        """Chamado pelo MainWindow ao alternar o tema (mesma convenção do
        DashboardPage) — só precisa lembrar o tema atual pro próximo popup
        que for aberto, já que o painel é recriado a cada clique no sino."""
        self._dark_mode = dark


class _NotificationPanel(QWidget):
    def __init__(self, api_client: ApiClient, session: UserSession, dark: bool, on_closed) -> None:
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        # Um popup top-level sem `WA_TranslucentBackground` pinta um retângulo
        # opaco do sistema por baixo — os cantos arredondados do QSS ficariam
        # "cortados" contra esse fundo quadrado. Com isso, só a própria forma
        # arredondada (pintada pela regra `QWidget#NotificationPanel` abaixo)
        # fica visível — MAS com a janela toda com canal alfa real, qualquer
        # filho estilizado como "transparent" (inclusive o viewport do
        # QScrollArea abaixo) vaza direto pro que está atrás da janela, não
        # só até o fundo já pintado do próprio painel. Por isso o viewport
        # recebe a cor sólida do tema (`palette.surface`) em vez de
        # "transparent": o filho FICA no lugar certo, com a mesma cor, sem
        # depender do "atrás dele" já estar opaco.
        #
        # Isso por si só não bastava (bug reportado duas vezes: painel "ainda
        # transparente" mesmo depois do ajuste do viewport acima). Tentativa 1
        # foi ligar `WA_StyledBackground` pra fazer o `QWidget` puro respeitar
        # a regra `QWidget#NotificationPanel {{ background: ... }}` do QSS —
        # não resolveu: nesta janela translúcida de topo, só a área do
        # scroll (que já pinta sua própria cor sólida diretamente, sem
        # depender de QSS) ficava opaca; a faixa do cabeçalho (título +
        # "Marcar todas como lidas", fora do QScrollArea) continuava vazando
        # pro desktop por trás — confirmado visualmente com uma janela-anfitriã
        # de fundo listrado colorido atrás do popup. `WA_StyledBackground` +
        # `WA_TranslucentBackground` juntos num widget de TOPO não é
        # confiável: o Qt não garante que o preenchimento do estilo cubra o
        # retângulo inteiro antes dos filhos pintarem por cima. A solução
        # robusta (e a recomendada pela própria documentação do Qt pra
        # janelas translúcidas com forma customizada) é pintar o fundo à mão
        # em `paintEvent`, em vez de confiar em QSS — ver `paintEvent` abaixo.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("NotificationPanel")
        self._api_client = api_client
        self._session = session
        self._palette = DARK if dark else LIGHT
        self._surface_color = QColor(self._palette.surface)
        self._border_color = QColor(self._palette.border)
        self._on_closed = on_closed
        self._worker: ApiWorker | None = None
        self._action_worker: ApiWorker | None = None
        # Tamanho fixo, com rolagem interna, em vez de tentar acompanhar o
        # tamanho do conteúdo: o painel abre e busca as notificações de forma
        # assíncrona, então "encolher/crescer conforme os dados chegam" é uma
        # corrida contra o layout do Qt (o sizeHint de um QScrollArea não
        # reflete o widget interno de qualquer forma — é o ponto de existir
        # rolagem). Um tamanho fixo com scroll é também o padrão real de
        # painéis de notificação (GitHub, Slack, etc.), não uma solução de
        # contorno.
        self.setFixedSize(380, 460)
        apply_shadow(self, blur=40, y_offset=14, alpha=35)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(14, 12, 10, 8)
        header.addWidget(QLabel("Notificações", objectName="SectionTitle"))
        header.addStretch(1)
        self._mark_all_button = QPushButton("Marcar todas como lidas", objectName="LinkButton")
        self._mark_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mark_all_button.clicked.connect(self._handle_mark_all_clicked)
        header.addWidget(self._mark_all_button)
        outer.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.viewport().setStyleSheet(f"background: {self._palette.surface};")
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(6, 0, 6, 10)
        self._list_layout.setSpacing(2)
        self._scroll.setWidget(self._list_container)
        outer.addWidget(self._scroll, stretch=1)

    def refresh(self) -> None:
        self._worker = ApiWorker(
            self._api_client.list_notifications, self._session.access_token, page_size=20,
        )
        self._worker.succeeded.connect(self._apply_notifications)
        self._worker.failed.connect(lambda _exc: self._show_empty("Não foi possível carregar as notificações."))
        self._worker.start()

    def _clear_list(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_empty(self, message: str) -> None:
        self._clear_list()
        label = QLabel(message, objectName="Muted")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        self._list_layout.addWidget(label)
        self._list_layout.addStretch(1)

    def _apply_notifications(self, result: dict) -> None:
        items = result.get("items", [])
        self._mark_all_button.setEnabled(any(item["read_at"] is None for item in items))
        if not items:
            self._show_empty("Nenhuma notificação por enquanto.\nOs robôs em background avisam aqui quando algo precisar da sua atenção.")
            return
        self._clear_list()
        for item in items:
            self._list_layout.addWidget(self._build_row(item))
        self._list_layout.addStretch(1)  # lista curta some no topo, não no meio da caixa

    def _build_row(self, item: dict) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)
        if item["read_at"] is None:
            container.setStyleSheet("background: rgba(67, 56, 202, 0.07); border-radius: 10px;")

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_label = QLabel(item["title"])
        title_font = title_label.font()
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_row.addWidget(title_label, stretch=1)
        severity_info = _SEVERITY_BADGE.get(item["severity"])
        if severity_info:
            title_row.addWidget(build_badge(*severity_info))
        layout.addLayout(title_row)

        message_label = QLabel(item["message"])
        message_label.setObjectName("Muted")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        time_label = QLabel(_relative_time(item["created_at"]), objectName="Faint")
        layout.addWidget(time_label)

        if item["read_at"] is None:
            notification_id = item["id"]
            mark_button = QPushButton("Marcar como lida", objectName="LinkButton")
            mark_button.setCursor(Qt.CursorShape.PointingHandCursor)
            mark_button.clicked.connect(lambda: self._handle_mark_read_clicked(notification_id))
            layout.addWidget(mark_button, alignment=Qt.AlignmentFlag.AlignLeft)

        return container

    def _handle_mark_read_clicked(self, notification_id: int) -> None:
        self._action_worker = ApiWorker(
            self._api_client.mark_notification_read, self._session.access_token, notification_id,
        )
        self._action_worker.succeeded.connect(lambda _r: self.refresh())
        self._action_worker.failed.connect(lambda _exc: None)
        self._action_worker.start()

    def _handle_mark_all_clicked(self) -> None:
        self._action_worker = ApiWorker(self._api_client.mark_all_notifications_read, self._session.access_token)
        self._action_worker.succeeded.connect(lambda _r: self.refresh())
        self._action_worker.failed.connect(lambda _exc: None)
        self._action_worker.start()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        """Pinta o fundo arredondado do painel manualmente em vez de confiar
        em QSS (ver o comentário longo no `__init__` sobre por que isso é
        necessário numa janela `WA_TranslucentBackground`)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(0, 0, -1, -1), 14, 14)
        painter.fillPath(path, self._surface_color)
        painter.setPen(QPen(self._border_color, 1))
        painter.drawPath(path)
        super().paintEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        super().closeEvent(event)
        self._on_closed()
