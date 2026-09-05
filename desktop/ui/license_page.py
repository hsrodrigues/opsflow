"""License screen (seção 6/7): plano atual, status e uso real vs. limite.

Só leitura — gerir a licença (renovar, trocar de plano) é uma operação de
plataforma (`SUPER_ADMIN`), que ainda não tem console próprio; esta tela é
a empresa acompanhando o próprio consumo, não administrando-o.
"""
from datetime import datetime, timezone

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.session import UserSession
from services.api_client import ApiClient
from services.async_task import ApiWorker
from services.errors import ApiError
from ui.theme import apply_shadow
from ui.widgets import build_badge

_STATUS_DISPLAY = {
    "ACTIVE": ("Ativa", "BadgeSuccess"), "TRIAL": ("Em teste", "BadgeWarning"),
    "SUSPENDED": ("Suspensa", "BadgeDanger"), "EXPIRED": ("Expirada", "BadgeDanger"),
    "CANCELLED": ("Cancelada", "BadgeDanger"),
}
_STATUS_BANNER = {
    "TRIAL": ("Você está em período de teste.", "LicenseBannerTrial"),
    "SUSPENDED": ("Licença suspensa — contate o suporte para reativar.", "LicenseBannerExpired"),
    "EXPIRED": ("Licença expirada — contate o suporte para renovar.", "LicenseBannerExpired"),
    "CANCELLED": ("Licença cancelada — contate o suporte.", "LicenseBannerExpired"),
}


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _expiry_text(expires_at_iso: str | None) -> str:
    if not expires_at_iso:
        return "Sem data de expiração definida."
    expires = datetime.fromisoformat(expires_at_iso.replace("Z", "+00:00"))
    now = datetime.now(expires.tzinfo) if expires.tzinfo else datetime.now(timezone.utc).replace(tzinfo=None)
    delta_days = (expires - now).days
    formatted = expires.strftime("%d/%m/%Y")
    if delta_days < 0:
        return f"Expirou em {formatted} (há {abs(delta_days)} dia(s))."
    if delta_days == 0:
        return f"Expira hoje ({formatted})."
    return f"Válida até {formatted} — {delta_days} dia(s) restante(s)."


class LicensePage(QWidget):
    def __init__(self, api_client: ApiClient, session: UserSession) -> None:
        super().__init__()
        self._api_client = api_client
        self._session = session
        self._worker: ApiWorker | None = None

        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        layout.addWidget(QLabel("Licença", objectName="PageTitle"))

        self._banner = QLabel("")
        self._banner.hide()
        layout.addWidget(self._banner)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)

        # --- cartão do plano ---
        plan_card = QFrame(objectName="Card")
        apply_shadow(plan_card, blur=20, y_offset=6, alpha=16)
        plan_layout = QVBoxLayout(plan_card)
        plan_layout.setContentsMargins(20, 18, 20, 18)
        plan_layout.setSpacing(4)

        plan_header = QHBoxLayout()
        self._plan_name_label = QLabel("—")
        self._plan_name_label.setStyleSheet("font-size: 22px; font-weight: 700;")
        plan_header.addWidget(self._plan_name_label)
        plan_header.addStretch(1)
        self._status_slot = QHBoxLayout()
        plan_header.addLayout(self._status_slot)
        plan_layout.addLayout(plan_header)

        self._expiry_label = QLabel("", objectName="Muted")
        plan_layout.addWidget(self._expiry_label)
        plan_layout.addStretch(1)
        cards_row.addWidget(plan_card, stretch=1)

        # --- cartão de uso ---
        usage_card = QFrame(objectName="Card")
        apply_shadow(usage_card, blur=20, y_offset=6, alpha=16)
        usage_layout = QVBoxLayout(usage_card)
        usage_layout.setContentsMargins(20, 18, 20, 18)
        usage_layout.setSpacing(16)
        usage_layout.addWidget(QLabel("Uso do plano", objectName="SectionTitle"))

        users_row, self._users_value_label, self._users_fill, self._users_track_layout = self._build_usage_row(
            "Usuários"
        )
        usage_layout.addWidget(users_row)
        vehicles_row, self._vehicles_value_label, self._vehicles_fill, self._vehicles_track_layout = (
            self._build_usage_row("Veículos")
        )
        usage_layout.addWidget(vehicles_row)
        usage_layout.addStretch(1)
        cards_row.addWidget(usage_card, stretch=1)

        layout.addLayout(cards_row)
        layout.addStretch(1)

    @staticmethod
    def _build_usage_row(label_text: str) -> tuple[QWidget, QLabel, QWidget, QHBoxLayout]:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label_row = QHBoxLayout()
        label_row.addWidget(QLabel(label_text))
        label_row.addStretch(1)
        value_label = QLabel("—", objectName="Muted")
        label_row.addWidget(value_label)
        layout.addLayout(label_row)

        track = QWidget(objectName="UsageBarTrack")
        track.setFixedHeight(8)
        track_layout = QHBoxLayout(track)
        track_layout.setContentsMargins(0, 0, 0, 0)
        track_layout.setSpacing(0)
        fill = QWidget(objectName="UsageBarFillNormal")
        spacer = QWidget()
        track_layout.addWidget(fill, 0)
        track_layout.addWidget(spacer, 1)
        layout.addWidget(track)

        return container, value_label, fill, track_layout

    @staticmethod
    def _update_usage_row(value_label: QLabel, fill: QWidget, track_layout: QHBoxLayout, used: int, limit: int | None) -> None:
        if limit is None:
            value_label.setText(f"{used} · sem limite")
            track_layout.setStretch(0, 0)
            track_layout.setStretch(1, 1)
            fill.setObjectName("UsageBarFillNormal")
            _repolish(fill)
            return

        value_label.setText(f"{used} / {limit}")
        ratio = used / limit if limit else 0
        variant = "UsageBarFillDanger" if ratio >= 1 else "UsageBarFillWarning" if ratio >= 0.8 else "UsageBarFillNormal"
        fill.setObjectName(variant)
        _repolish(fill)
        used_stretch = max(min(used, limit), 0)
        remaining_stretch = max(limit - used, 0)
        if used_stretch == 0 and remaining_stretch == 0:
            remaining_stretch = 1
        track_layout.setStretch(0, used_stretch)
        track_layout.setStretch(1, remaining_stretch)

    def _load(self) -> None:
        self._worker = ApiWorker(self._api_client.get_license, self._session.access_token)
        self._worker.succeeded.connect(self._apply_summary)
        self._worker.failed.connect(self._handle_load_failed)
        self._worker.start()

    def _apply_summary(self, summary: dict) -> None:
        self._plan_name_label.setText(summary["plan_name"])

        while self._status_slot.count():
            item = self._status_slot.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        text, badge_class = _STATUS_DISPLAY.get(summary["status"], (summary["status"], "BadgeNeutral"))
        self._status_slot.addWidget(build_badge(text, badge_class))

        self._expiry_label.setText(_expiry_text(summary.get("expires_at")))

        banner = _STATUS_BANNER.get(summary["status"])
        if banner:
            text, style = banner
            self._banner.setText(f"ℹ {text}")
            self._banner.setObjectName(style)
            _repolish(self._banner)
            self._banner.show()
        else:
            self._banner.hide()

        self._update_usage_row(
            self._users_value_label, self._users_fill, self._users_track_layout,
            summary["current_users"], summary["max_users"],
        )
        self._update_usage_row(
            self._vehicles_value_label, self._vehicles_fill, self._vehicles_track_layout,
            summary["current_vehicles"], summary["max_vehicles"],
        )

    def _handle_load_failed(self, exc: Exception) -> None:
        message = exc.friendly_message if isinstance(exc, ApiError) else "Não foi possível carregar a licença."
        self._plan_name_label.setText(message)
