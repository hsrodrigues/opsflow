"""Visual identity (seção 26/56): a dark sidebar + light/dark content area,
a single accent color, and enough spacing/typography discipline to read as
a real product rather than a default Qt window.

Two palettes (`LIGHT`/`DARK`) drive one QSS template — switching theme at
runtime (seção 26: "Tema: claro; escuro") is just re-rendering the same
template with the other palette, applied to the whole `QApplication`.
"""
from dataclasses import dataclass

from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Palette:
    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    sidebar_bg: str
    sidebar_text: str
    sidebar_text_muted: str
    sidebar_active: str
    accent: str
    accent_hover: str
    accent_text: str
    success: str
    warning: str
    danger: str


LIGHT = Palette(
    bg="#F4F6F9", surface="#FFFFFF", surface_alt="#F0F2F5", border="#E2E6EC",
    text="#1B2430", text_muted="#64748B", sidebar_bg="#161E2C", sidebar_text="#E7EBF3",
    sidebar_text_muted="#8B93A7", sidebar_active="#243247", accent="#2F6FED",
    accent_hover="#255BC4", accent_text="#FFFFFF", success="#1D9E6E", warning="#D8912B",
    danger="#D64545",
)

DARK = Palette(
    bg="#10141B", surface="#171C26", surface_alt="#1D2330", border="#2A3142",
    text="#E7EBF3", text_muted="#8B93A7", sidebar_bg="#0B0F16", sidebar_text="#E7EBF3",
    sidebar_text_muted="#7C8497", sidebar_active="#1C2739", accent="#4C86FF",
    accent_hover="#6C9BFF", accent_text="#0B0F16", success="#33C08A", warning="#E3A94A",
    danger="#E9615F",
)


def _rgba(hex_color: str, alpha: float) -> str:
    """`#RRGGBB` + alpha (0-1) -> `rgba(r, g, b, a)`.

    Qt Style Sheets do NOT understand CSS3's 8-digit hex-with-alpha
    (`#RRGGBB22`) — QSS predates that syntax and silently mis-parses it, so
    every translucent color here must go through this instead.
    """
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha})"


def build_stylesheet(p: Palette) -> str:
    danger_wash, danger_border = _rgba(p.danger, 0.13), _rgba(p.danger, 0.35)
    warning_wash, warning_border = _rgba(p.warning, 0.13), _rgba(p.warning, 0.35)
    return f"""
    * {{
        font-family: "Segoe UI", "Inter", sans-serif;
        font-size: 13px;
        color: {p.text};
    }}
    QWidget#AppRoot, QMainWindow {{ background: {p.bg}; }}
    QWidget#LoginCard {{
        background: {p.surface};
        border-radius: 12px;
        border: 1px solid {p.border};
    }}
    QWidget#Sidebar {{ background: {p.sidebar_bg}; }}
    QLabel#SidebarBrand {{
        color: {p.sidebar_text}; font-size: 18px; font-weight: 600; padding: 4px 0 2px 0;
    }}
    QLabel#SidebarTagline {{ color: {p.sidebar_text_muted}; font-size: 11px; }}
    QPushButton#NavItem {{
        color: {p.sidebar_text_muted}; background: transparent; border: none;
        text-align: left; padding: 10px 16px; border-radius: 8px; font-size: 13px;
    }}
    QPushButton#NavItem:hover {{ background: {p.sidebar_active}; color: {p.sidebar_text}; }}
    QPushButton#NavItem:checked {{ background: {p.sidebar_active}; color: {p.sidebar_text}; font-weight: 600; }}
    QWidget#Topbar {{ background: {p.surface}; border-bottom: 1px solid {p.border}; }}
    QWidget#StatusBar {{ background: {p.surface}; border-top: 1px solid {p.border}; }}
    QLabel#PageTitle {{ font-size: 20px; font-weight: 600; }}
    QLabel#Muted {{ color: {p.text_muted}; }}
    QLabel#StatusOnline {{ color: {p.success}; font-weight: 600; }}
    QLabel#StatusOffline {{ color: {p.danger}; font-weight: 600; }}
    QFrame#Card {{
        background: {p.surface}; border: 1px solid {p.border}; border-radius: 10px;
    }}
    QLabel#CardValue {{ font-size: 26px; font-weight: 700; }}
    QLabel#CardLabel {{ color: {p.text_muted}; font-size: 12px; }}
    QLineEdit {{
        background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: 8px;
        padding: 9px 12px; selection-background-color: {p.accent};
    }}
    QLineEdit:focus {{ border: 1px solid {p.accent}; }}
    QPushButton#PrimaryButton {{
        background: {p.accent}; color: {p.accent_text}; border: none; border-radius: 8px;
        padding: 10px 16px; font-weight: 600;
    }}
    QPushButton#PrimaryButton:hover {{ background: {p.accent_hover}; }}
    QPushButton#PrimaryButton:disabled {{ background: {p.border}; color: {p.text_muted}; }}
    QPushButton#LinkButton {{
        background: transparent; border: none; color: {p.accent}; text-align: left;
    }}
    QPushButton#LinkButton:hover {{ text-decoration: underline; }}
    QPushButton#IconButton {{
        background: transparent; border: none; border-radius: 8px; padding: 6px;
    }}
    QPushButton#IconButton:hover {{ background: {p.surface_alt}; }}
    QLabel#ErrorBanner {{
        background: {danger_wash}; color: {p.danger}; border: 1px solid {danger_border};
        border-radius: 8px; padding: 8px 12px;
    }}
    QLabel#LicenseBannerTrial {{
        background: {warning_wash}; color: {p.warning}; border: 1px solid {warning_border};
        border-radius: 8px; padding: 8px 12px;
    }}
    QLabel#LicenseBannerExpired {{
        background: {danger_wash}; color: {p.danger}; border: 1px solid {danger_border};
        border-radius: 8px; padding: 8px 12px;
    }}
    QCheckBox {{ spacing: 8px; }}
    """


def apply_theme(app: QApplication, *, dark: bool) -> Palette:
    palette = DARK if dark else LIGHT
    app.setStyleSheet(build_stylesheet(palette))
    return palette
