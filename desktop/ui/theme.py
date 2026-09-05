"""Visual identity (seção 26/56): a real design system, not a default-Qt
window with a couple of styled buttons.

Every widget type actually used anywhere in the app is styled here —
inputs, combos, spin boxes, checkboxes, tables, dialogs, scrollbars,
tooltips — because a single unstyled native control (a plain OS combobox
next to a flat rounded text field, say) is enough to make the whole screen
read as unfinished. Two palettes (`LIGHT`/`DARK`) drive one QSS template;
switching theme at runtime (seção 26) just re-renders the same template
with the other palette, applied to the whole `QApplication`. `apply_shadow`
adds the soft elevation QSS itself cannot express (`box-shadow` has no Qt
Style Sheets equivalent) via `QGraphicsDropShadowEffect`.

The look leans into a "fintech" register (Stripe/Nubank/Revolut-style
dashboards) rather than flat default-Qt: a two-tone indigo→violet gradient
(instead of one flat accent) drives the primary CTA, the brand mark and the
login screen's brand panel; corners are generously rounded (12-28px
depending on the element's size, buttons go full pill); and elevation uses
a soft accent-tinted glow on the highest-emphasis surfaces instead of a
plain black drop shadow everywhere.
"""
from dataclasses import dataclass

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QScrollArea, QWidget


@dataclass(frozen=True)
class Palette:
    bg: str
    surface: str
    surface_alt: str
    surface_hover: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_faint: str
    sidebar_bg: str
    sidebar_bg_end: str
    sidebar_text: str
    sidebar_text_muted: str
    sidebar_active: str
    accent: str
    accent2: str
    accent_hover: str
    accent_pressed: str
    accent_text: str
    success: str
    warning: str
    danger: str
    shadow: str


LIGHT = Palette(
    bg="#F5F6F8", surface="#FFFFFF", surface_alt="#F1F3F6", surface_hover="#E9ECF1",
    border="#E3E6EC", border_strong="#CBD2DE",
    text="#101828", text_muted="#5B6474", text_faint="#98A2B3",
    sidebar_bg="#111827", sidebar_bg_end="#0B1120",
    sidebar_text="#F0F2F7", sidebar_text_muted="#8891A5", sidebar_active="#1D2436",
    accent="#4338CA", accent2="#7C3AED", accent_hover="#372DAD", accent_pressed="#2E2590", accent_text="#FFFFFF",
    success="#0B8A5E", warning="#B45E09", danger="#C42B2B",
    shadow="#0F1A2E",
)

DARK = Palette(
    bg="#0B0F1A", surface="#131A29", surface_alt="#1A2233", surface_hover="#212B40",
    border="#242E45", border_strong="#33405C",
    text="#E7EAF2", text_muted="#909BB0", text_faint="#5D6981",
    sidebar_bg="#080B13", sidebar_bg_end="#0B1120",
    sidebar_text="#EDEFF5", sidebar_text_muted="#6B7590", sidebar_active="#1B2333",
    accent="#6366F1", accent2="#8B5CFF", accent_hover="#7A7DF5", accent_pressed="#5457D8", accent_text="#0B0F1A",
    success="#2FBF8F", warning="#E8A93D", danger="#F0645F",
    shadow="#000000",
)

# Painel de marca do login (seção 5): gradiente fixo, independente do tema
# claro/escuro — como em telas de autenticação de apps fintech, a cor de
# marca não muda com o tema do sistema, só o painel do formulário muda.
_BRAND_GRADIENT = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4338CA, stop:0.55 #6D28D9, stop:1 #1E1B4B)"

# Pares de cor (início/fim do gradiente) para os "chips" de ícone dos
# cartões de indicador (KPI) — fixos nos dois temas, como os badges de
# status, porque carregam significado semântico (sucesso/alerta/perigo).
_ICON_CHIP_GRADIENTS = {
    "IconChipInfo": ("#4338CA", "#7C3AED"),
    "IconChipSuccess": ("#059669", "#10B981"),
    "IconChipWarning": ("#D97706", "#F59E0B"),
    "IconChipDanger": ("#DC2626", "#F43F5E"),
    "IconChipNeutral": ("#475569", "#64748B"),
}


def _rgba(hex_color: str, alpha: float) -> str:
    """`#RRGGBB` + alpha (0-1) -> `rgba(r, g, b, a)`.

    Qt Style Sheets do NOT understand CSS3's 8-digit hex-with-alpha
    (`#RRGGBB22`) — QSS predates that syntax and silently mis-parses it, so
    every translucent color here must go through this instead.
    """
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha})"


def _gradient(c1: str, c2: str, *, diagonal: bool = True) -> str:
    """Two-stop QSS gradient — `qlineargradient` is a native Qt Style Sheets
    property (not CSS), used for the brand's signature indigo→violet accent
    instead of a single flat fill.
    """
    x2, y2 = (1, 1) if diagonal else (0, 1)
    return f"qlineargradient(x1:0, y1:0, x2:{x2}, y2:{y2}, stop:0 {c1}, stop:1 {c2})"


_DOWN_ARROW_SVG = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'>"
    "<path d='M1 1l4 4 4-4' stroke='{color}' stroke-width='1.6' fill='none' "
    "stroke-linecap='round' stroke-linejoin='round'/></svg>"
)


def build_stylesheet(p: Palette) -> str:
    accent_wash = _rgba(p.accent, 0.10)
    accent_wash_strong = _rgba(p.accent, 0.18)
    danger_wash, danger_border = _rgba(p.danger, 0.12), _rgba(p.danger, 0.35)
    warning_wash, warning_border = _rgba(p.warning, 0.14), _rgba(p.warning, 0.35)
    success_wash = _rgba(p.success, 0.14)
    focus_ring = _rgba(p.accent, 0.22)
    down_arrow = _DOWN_ARROW_SVG.format(color=p.text_muted.replace("#", "%23"))
    accent_gradient = _gradient(p.accent, p.accent2)
    accent_gradient_hover = _gradient(p.accent_hover, p.accent2)
    accent_gradient_pressed = _gradient(p.accent_pressed, p.accent2)

    icon_chip_rules = "\n".join(
        f"    QWidget#{name} {{ background: {_gradient(c1, c2)}; border-radius: 14px; }}"
        for name, (c1, c2) in _ICON_CHIP_GRADIENTS.items()
    )

    return f"""
    * {{
        font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
        font-size: 13px;
        color: {p.text};
        outline: none;
    }}

    /* ---------- fundo geral ---------- */
    QWidget#AppRoot, QMainWindow, QDialog {{ background: {p.bg}; }}
    QToolTip {{
        background: {p.text}; color: {p.bg}; border: none; border-radius: 6px;
        padding: 6px 10px; font-size: 12px;
    }}

    /* ---------- tela de login: painel de marca ---------- */
    QWidget#LoginBrandPanel {{ background: {_BRAND_GRADIENT}; }}
    QWidget#LoginBrandBlob {{ background: {_rgba('#FFFFFF', 0.07)}; border-radius: 999px; }}
    QWidget#LoginFormPanel {{ background: {p.bg}; }}
    QLabel#LoginBrandKicker {{
        color: {_rgba('#FFFFFF', 0.78)}; font-size: 11.5px; font-weight: 700; letter-spacing: 2.5px;
    }}
    QLabel#LoginHeadline {{
        color: #FFFFFF; font-size: 34px; font-weight: 800; letter-spacing: -0.6px;
    }}
    QLabel#LoginSubheadline {{
        color: {_rgba('#FFFFFF', 0.74)}; font-size: 14.5px;
    }}
    QWidget#LoginFeatureIcon {{
        background: {_rgba('#FFFFFF', 0.12)}; border: 1px solid {_rgba('#FFFFFF', 0.20)}; border-radius: 12px;
    }}
    QLabel#LoginFeatureGlyph {{ font-size: 17px; }}
    QLabel#LoginFeatureTitle {{ color: #FFFFFF; font-size: 13px; font-weight: 700; }}
    QLabel#LoginFeatureDesc {{ color: {_rgba('#FFFFFF', 0.62)}; font-size: 12px; }}

    /* ---------- cartão de login ---------- */
    QWidget#LoginCard {{
        background: {p.surface};
        border-radius: 24px;
        border: 1px solid {p.border};
    }}
    QWidget#LoginLogo {{
        background: {accent_gradient};
        border-radius: 14px;
    }}
    QLabel#LoginLogoGlyph {{ color: {p.accent_text}; font-size: 22px; font-weight: 700; }}

    /* Painel de notificações (seção 20): NÃO estilizado aqui de propósito.
    É um QWidget de topo com WA_TranslucentBackground, e essa combinação não
    pinta um `background` de QSS de forma confiável (o fundo arredondado é
    pintado à mão no `paintEvent` de `ui/notification_panel.py`, que lê estas
    mesmas cores — `Palette.surface`/`Palette.border` — direto do Python). */

    /* ---------- barra lateral ---------- */
    QWidget#Sidebar {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {p.sidebar_bg}, stop:1 {p.sidebar_bg_end});
        border-right: 1px solid {_rgba('#000000', 0.25)};
    }}
    QLabel#SidebarBrand {{
        color: {p.sidebar_text}; font-size: 17px; font-weight: 700; padding: 4px 0 1px 0;
        letter-spacing: 0.5px;
    }}
    QLabel#SidebarTagline {{ color: {p.sidebar_text_muted}; font-size: 10.5px; letter-spacing: 0.3px; }}
    QLabel#SidebarSection {{
        color: {p.sidebar_text_muted}; font-size: 10.5px; font-weight: 700; letter-spacing: 1px;
        padding: 14px 12px 4px 12px;
    }}
    QPushButton#NavItem {{
        color: {p.sidebar_text_muted}; background: transparent; border: none; border-left: 3px solid transparent;
        text-align: left; padding: 9px 16px 9px 13px; border-radius: 0px; font-size: 13px; margin: 1px 8px 1px 0;
    }}
    QPushButton#NavItem:hover {{ background: {_rgba('#FFFFFF', 0.05)}; color: {p.sidebar_text}; }}
    QPushButton#NavItem:checked {{
        background: {_rgba('#FFFFFF', 0.07)}; color: {p.sidebar_text}; font-weight: 600;
        border-left: 3px solid {p.accent2};
    }}
    QPushButton#NavItem:disabled {{ color: {p.sidebar_text_muted}; }}

    /* ---------- topbar / status bar ---------- */
    QWidget#Topbar {{ background: {p.surface}; border-bottom: 1px solid {p.border}; }}
    QWidget#StatusBar {{ background: {p.surface}; border-top: 1px solid {p.border}; }}
    QLabel#PageTitle {{ font-size: 19px; font-weight: 700; letter-spacing: 0.2px; }}
    QLabel#SectionTitle {{ font-size: 15px; font-weight: 700; }}
    QLabel#Muted {{ color: {p.text_muted}; }}
    QLabel#Faint {{ color: {p.text_faint}; font-size: 11.5px; }}
    QLabel#StatusOnline {{ color: {p.success}; font-weight: 600; }}
    QLabel#StatusOffline {{ color: {p.danger}; font-weight: 600; }}
    QLabel#Avatar {{
        background: {accent_gradient}; color: {p.accent_text}; border-radius: 15px; font-weight: 700; font-size: 12px;
    }}

    /* ---------- cartões ---------- */
    QFrame#Card {{
        background: {p.surface}; border: 1px solid {p.border}; border-radius: 16px;
    }}
    QLabel#CardValue {{ font-size: 26px; font-weight: 700; letter-spacing: -0.5px; }}
    QLabel#CardLabel {{ color: {p.text_muted}; font-size: 11.5px; font-weight: 600; letter-spacing: 0.3px; }}

    /* ---------- chips de ícone dos cartões de indicador (KPI) ---------- */
{icon_chip_rules}
    QLabel#IconChipGlyph {{ font-size: 19px; }}

    /* ---------- barra de uso do plano (tela de Licença) ---------- */
    QWidget#UsageBarTrack {{ background: {p.surface_alt}; border-radius: 4px; }}
    QWidget#UsageBarFillNormal {{ background: {accent_gradient}; border-radius: 4px; }}
    QWidget#UsageBarFillWarning {{ background: {p.warning}; border-radius: 4px; }}
    QWidget#UsageBarFillDanger {{ background: {p.danger}; border-radius: 4px; }}

    /* ---------- badges de status (pill) ---------- */
    QLabel[badge="true"] {{
        border-radius: 10px; padding: 3px 10px; font-size: 11.5px; font-weight: 600;
    }}
    QLabel#BadgeSuccess {{ background: {success_wash}; color: {p.success}; }}
    QLabel#BadgeInfo {{ background: {accent_wash_strong}; color: {p.accent}; }}
    QLabel#BadgeWarning {{ background: {warning_wash}; color: {p.warning}; }}
    QLabel#BadgeDanger {{ background: {danger_wash}; color: {p.danger}; }}
    QLabel#BadgeNeutral {{ background: {p.surface_alt}; color: {p.text_muted}; }}

    /* ---------- campos de formulário ---------- */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit, QTextEdit {{
        background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: 12px;
        padding: 9px 12px; selection-background-color: {p.accent}; selection-color: {p.accent_text};
        min-height: 18px;
    }}
    /* O texto "dd/MM/yyyy HH:mm" + o botão do calendário (28px, ver
       `::drop-down` abaixo) não cabem no sizeHint padrão que o Qt calcula
       pra esses widgets quando não têm largura própria definida (ex.: os
       filtros de período do Dashboard/Programação) — sem isto, o fim do ano
       fica cortado atrás do botão. */
    QDateEdit, QDateTimeEdit {{ min-width: 152px; }}
    QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover,
    QDateEdit:hover, QDateTimeEdit:hover {{ border: 1px solid {p.border_strong}; }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
    QDateEdit:focus, QDateTimeEdit:focus, QTextEdit:focus {{
        border: 1px solid {p.accent}; background: {p.surface};
    }}
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
    QDateEdit:disabled, QDateTimeEdit:disabled {{
        background: {p.surface_alt}; color: {p.text_faint}; border: 1px solid {p.border};
    }}
    QComboBox::drop-down, QDateEdit::drop-down, QDateTimeEdit::drop-down {{ border: none; width: 28px; }}
    QComboBox::down-arrow, QDateEdit::down-arrow, QDateTimeEdit::down-arrow {{
        image: url("{down_arrow}"); width: 10px; height: 6px;
    }}
    QComboBox QAbstractItemView {{
        background: {p.surface}; border: 1px solid {p.border}; border-radius: 10px; padding: 4px;
        selection-background-color: {accent_wash_strong}; selection-color: {p.accent}; outline: none;
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        subcontrol-position: top right; width: 20px; border: none; border-top-right-radius: 12px;
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        subcontrol-position: bottom right; width: 20px; border: none; border-bottom-right-radius: 12px;
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background: {p.surface_hover}; }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url("{down_arrow}"); width: 8px; height: 5px; }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url("{down_arrow}"); width: 8px; height: 5px; }}

    /* ---------- calendário (popup do QDateEdit/QDateTimeEdit) ---------- */
    QCalendarWidget {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 12px; }}
    QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {p.surface_alt}; border-top-left-radius: 12px; border-top-right-radius: 12px; }}
    QCalendarWidget QToolButton {{
        background: transparent; color: {p.text}; border: none; border-radius: 8px;
        padding: 6px 8px; font-weight: 600; icon-size: 16px, 16px;
    }}
    QCalendarWidget QToolButton:hover {{ background: {p.surface_hover}; }}
    QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
    QCalendarWidget QSpinBox {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 6px; padding: 2px 4px; }}
    QCalendarWidget QAbstractItemView {{
        background: {p.surface}; color: {p.text}; selection-background-color: {p.accent};
        selection-color: {p.accent_text}; outline: none; border: none;
        alternate-background-color: {p.surface};
    }}
    QCalendarWidget QAbstractItemView:disabled {{ color: {p.text_faint}; }}
    QCalendarWidget QMenu {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 10px; }}

    QCheckBox {{ spacing: 9px; }}
    QCheckBox::indicator {{
        width: 17px; height: 17px; border-radius: 5px; border: 1.5px solid {p.border_strong};
        background: {p.surface};
    }}
    QCheckBox::indicator:hover {{ border: 1.5px solid {p.accent}; }}
    QCheckBox::indicator:checked {{
        background: {p.accent}; border: 1.5px solid {p.accent};
        image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='9'>"
        "<path d='M1 4.5l3 3 7-7' stroke='{p.accent_text.replace('#', '%23')}' stroke-width='1.8' "
        "fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>");
    }}

    /* ---------- botões ---------- */
    QPushButton#PrimaryButton {{
        background: {accent_gradient}; color: {p.accent_text}; border: none; border-radius: 20px;
        padding: 11px 22px; font-weight: 700; letter-spacing: 0.2px;
    }}
    QPushButton#PrimaryButton:hover {{ background: {accent_gradient_hover}; }}
    QPushButton#PrimaryButton:pressed {{ background: {accent_gradient_pressed}; }}
    QPushButton#PrimaryButton:disabled {{ background: {p.border}; color: {p.text_faint}; }}

    QPushButton#SecondaryButton {{
        background: {p.surface}; color: {p.text}; border: 1px solid {p.border_strong}; border-radius: 20px;
        padding: 10px 21px; font-weight: 600;
    }}
    QPushButton#SecondaryButton:hover {{ background: {p.surface_hover}; }}
    QPushButton#SecondaryButton:pressed {{ background: {p.surface_alt}; }}

    QPushButton#DangerButton {{
        background: {p.danger}; color: #FFFFFF; border: none; border-radius: 20px;
        padding: 11px 22px; font-weight: 700;
    }}
    QPushButton#DangerButton:hover {{ background: {p.danger}; }}

    QPushButton#LinkButton {{
        background: transparent; border: none; color: {p.accent}; text-align: left; font-weight: 600;
        padding: 4px 6px; border-radius: 6px;
    }}
    QPushButton#LinkButton:hover {{ background: {accent_wash}; }}
    QPushButton#LinkButton:disabled {{ color: {p.text_faint}; }}

    QPushButton#DangerLinkButton {{
        background: transparent; border: none; color: {p.danger}; text-align: left; font-weight: 600;
        padding: 4px 6px; border-radius: 6px;
    }}
    QPushButton#DangerLinkButton:hover {{ background: {danger_wash}; }}

    QPushButton#IconButton {{
        background: transparent; border: none; border-radius: 16px; padding: 6px;
    }}
    QPushButton#IconButton:hover {{ background: {p.surface_alt}; }}

    /* ---------- avisos ---------- */
    QLabel#ErrorBanner {{
        background: {danger_wash}; color: {p.danger}; border: 1px solid {danger_border};
        border-radius: 12px; padding: 10px 14px; font-weight: 500;
    }}
    QLabel#LicenseBannerTrial {{
        background: {warning_wash}; color: {p.warning}; border: 1px solid {warning_border};
        border-radius: 12px; padding: 10px 14px; font-weight: 500;
    }}
    QLabel#LicenseBannerExpired {{
        background: {danger_wash}; color: {p.danger}; border: 1px solid {danger_border};
        border-radius: 12px; padding: 10px 14px; font-weight: 500;
    }}

    /* ---------- tabela ---------- */
    QTableWidget {{
        background: {p.surface}; alternate-background-color: {p.surface_alt};
        gridline-color: transparent; border: 1px solid {p.border}; border-radius: 16px;
        selection-background-color: {accent_wash_strong}; selection-color: {p.text};
    }}
    QTableWidget::item {{ padding: 8px 4px; border-bottom: 1px solid {p.border}; }}
    QTableWidget::item:selected {{ background: {accent_wash}; color: {p.text}; }}
    QHeaderView::section {{
        background: {p.surface_alt}; color: {p.text_muted}; padding: 10px 8px; border: none;
        border-bottom: 1px solid {p.border}; font-weight: 700; font-size: 11px; letter-spacing: 0.4px;
    }}
    QHeaderView::section:first {{ border-top-left-radius: 16px; }}
    QHeaderView::section:last {{ border-top-right-radius: 16px; }}
    QTableCornerButton::section {{ background: {p.surface_alt}; border: none; }}

    /* ---------- barras de rolagem ---------- */
    QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
    QScrollBar::handle:vertical {{
        background: {p.border_strong}; border-radius: 5px; min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {p.text_faint}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {p.border_strong}; border-radius: 5px; min-width: 32px; }}
    QScrollBar::handle:horizontal:hover {{ background: {p.text_faint}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* ---------- caixas de diálogo do sistema ---------- */
    QMessageBox {{ background: {p.surface}; }}
    QMessageBox QLabel {{ color: {p.text}; }}
    QMessageBox QPushButton {{
        background: {p.surface_alt}; border: 1px solid {p.border_strong}; border-radius: 8px;
        padding: 7px 16px; min-width: 72px; font-weight: 600;
    }}
    QMessageBox QPushButton:hover {{ background: {p.surface_hover}; }}
    QMessageBox QPushButton[text="Yes"], QMessageBox QPushButton[text="&Yes"] {{
        background: {p.danger}; color: #FFFFFF; border: none;
    }}
    """


def apply_theme(app: QApplication, *, dark: bool) -> Palette:
    palette = DARK if dark else LIGHT
    app.setStyleSheet(build_stylesheet(palette))
    return palette


def make_scroll_area_transparent(scroll: QScrollArea) -> None:
    """`QScrollArea`'s internal viewport is a separate widget that paints its
    own native palette background regardless of the app's QSS — the same
    "follows the OS theme, not the app theme" bug as `QChartView`
    (`dashboard_page.py`'s `_build_chart_placeholder`), just for a different
    Qt widget family. Unlike that one, this can't even be fixed via QSS
    selectors at all (confirmed: neither `QScrollArea { background: ... }`
    nor a `QScrollArea > QWidget` child selector reaches the viewport when
    set through `QApplication.setStyleSheet`) — the viewport's own
    stylesheet has to be set directly, procedurally, which is what this
    does. Call once, right after constructing the `QScrollArea`.
    """
    scroll.viewport().setStyleSheet("background: transparent;")


def apply_shadow(
    widget: QWidget, *, blur: int = 28, y_offset: int = 8, alpha: int = 45,
    color: tuple[int, int, int] = (0, 0, 0),
) -> None:
    """Soft drop shadow (Qt Style Sheets has no `box-shadow` equivalent).

    `color` defaults to black (a conventional neutral elevation shadow);
    pass an accent RGB tuple for the colored "glow" used on high-emphasis
    surfaces like the login card.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    r, g, b = color
    effect.setColor(QColor(r, g, b, alpha))
    widget.setGraphicsEffect(effect)
