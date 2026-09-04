"""Dashboard screen — welcome, license status, and quick account stats.

A real dashboard with operational KPIs (seção 15) is Fase 5; this is the
landing page every user sees right after login.
"""
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from app.session import UserSession
from ui.theme import apply_shadow

_ROLE_LABELS = {
    "SUPER_ADMIN": "Administrador da Plataforma",
    "ADMIN_EMPRESA": "Administrador",
    "SUPERVISOR": "Supervisor",
    "OPERADOR": "Operador",
    "VISUALIZADOR": "Visualizador",
}

_LICENSE_LABELS = {
    "ACTIVE": ("Licença ativa", None),
    "TRIAL": ("Você está em período de teste.", "LicenseBannerTrial"),
    "SUSPENDED": ("Licença suspensa — contate o suporte para reativar.", "LicenseBannerExpired"),
    "EXPIRED": ("Licença expirada — contate o suporte para renovar.", "LicenseBannerExpired"),
    "CANCELLED": ("Licença cancelada — contate o suporte.", "LicenseBannerExpired"),
}


def _repolish(widget: QWidget) -> None:
    """See the identical helper/docstring in `ui/main_window.py`."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class DashboardPage(QWidget):
    def __init__(self, session: UserSession) -> None:
        super().__init__()
        self._session = session
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        self._license_banner = QLabel("")
        self._license_banner.hide()
        layout.addWidget(self._license_banner)

        self._welcome_label = QLabel("", objectName="PageTitle")
        layout.addWidget(self._welcome_label)

        self._subtitle_label = QLabel("", objectName="Muted")
        layout.addWidget(self._subtitle_label)
        layout.addSpacing(8)

        self._cards_grid = QGridLayout()
        self._cards_grid.setSpacing(16)
        layout.addLayout(self._cards_grid)

        layout.addStretch(1)

    def _populate(self) -> None:
        self._welcome_label.setText(f"Bem-vindo, {self._session.full_name}")
        role_labels = ", ".join(_ROLE_LABELS.get(r, r) for r in self._session.roles) or "—"
        self._subtitle_label.setText(f"{self._session.email} · {role_labels}")

        if self._session.license_status:
            text, style = _LICENSE_LABELS.get(self._session.license_status, (self._session.license_status, None))
            self._license_banner.setText(f"ℹ {text}")
            self._license_banner.setObjectName(style or "Muted")
            self._license_banner.setVisible(style is not None)
            _repolish(self._license_banner)

        cards = [
            ("Plano", self._session.license_plan_code or "—"),
            ("Status da licença", self._session.license_status or "—"),
            ("Permissões concedidas", str(len(self._session.permissions))),
            ("Papéis", str(len(self._session.roles))),
        ]
        for index, (label, value) in enumerate(cards):
            self._cards_grid.addWidget(self._build_stat_card(label, value), 0, index)

    @staticmethod
    def _build_stat_card(label: str, value: str) -> QFrame:
        card = QFrame(objectName="Card")
        apply_shadow(card, blur=18, y_offset=4, alpha=18)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.addWidget(QLabel(value, objectName="CardValue"))
        layout.addWidget(QLabel(label, objectName="CardLabel"))
        return card
