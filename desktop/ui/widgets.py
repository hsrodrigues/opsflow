"""Small reusable widget builders shared across list screens."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


def build_badge(text: str, badge_class: str) -> QWidget:
    """A pill-shaped status label (`BadgeSuccess`/`BadgeInfo`/`BadgeWarning`/
    `BadgeDanger`/`BadgeNeutral` — styled in `ui/theme.py`), left-aligned
    inside its table cell.
    """
    label = QLabel(text, objectName=badge_class)
    label.setProperty("badge", "true")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(8, 0, 0, 0)
    layout.addWidget(label)
    layout.addStretch(1)
    return container
