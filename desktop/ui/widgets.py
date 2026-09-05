"""Small reusable widget builders shared across list screens and dialogs."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.theme import apply_shadow


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


def build_kpi_card(glyph: str, chip_variant: str, label: str) -> tuple[QFrame, QLabel]:
    """A KPI/indicator card: gradient icon chip + big value + small label,
    used on the Dashboard and the Centro de Operações board. `chip_variant`
    is one of `IconChipInfo`/`Success`/`Warning`/`Danger`/`Neutral` (styled
    in `ui/theme.py`). Returns `(card, value_label)` so the caller can keep
    a reference to update the value later.
    """
    card = QFrame(objectName="Card")
    apply_shadow(card, blur=20, y_offset=6, alpha=16)
    row = QHBoxLayout(card)
    row.setContentsMargins(18, 16, 18, 16)
    row.setSpacing(14)

    chip = QWidget(objectName=chip_variant)
    chip.setFixedSize(44, 44)
    chip_layout = QVBoxLayout(chip)
    chip_layout.setContentsMargins(0, 0, 0, 0)
    glyph_label = QLabel(glyph, objectName="IconChipGlyph")
    glyph_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    chip_layout.addWidget(glyph_label)
    row.addWidget(chip)

    text_col = QVBoxLayout()
    text_col.setSpacing(1)
    value_label = QLabel("—", objectName="CardValue")
    text_col.addWidget(value_label)
    text_col.addWidget(QLabel(label, objectName="CardLabel"))
    row.addLayout(text_col, stretch=1)

    return card, value_label


def build_dialog_header(glyph: str, chip_variant: str, title: str, subtitle: str) -> QWidget:
    """The in-content header every create/edit dialog opens with — an icon
    chip + bold title + muted subtitle — used instead of a bare form
    dropped straight under the OS title bar, which is what made every
    dialog in the app read as a plain, unbranded system prompt.
    """
    header = QWidget()
    row = QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(14)

    chip = QWidget(objectName=chip_variant)
    chip.setFixedSize(42, 42)
    chip_layout = QVBoxLayout(chip)
    chip_layout.setContentsMargins(0, 0, 0, 0)
    glyph_label = QLabel(glyph, objectName="IconChipGlyph")
    glyph_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    chip_layout.addWidget(glyph_label)
    row.addWidget(chip)

    text_col = QVBoxLayout()
    text_col.setSpacing(1)
    title_label = QLabel(title)
    title_label.setStyleSheet("font-size: 16px; font-weight: 700;")
    text_col.addWidget(title_label)
    text_col.addWidget(QLabel(subtitle, objectName="Muted"))
    row.addLayout(text_col, stretch=1)

    return header


def build_dialog_buttons(confirm_text: str = "Salvar") -> QDialogButtonBox:
    """The Save/Cancel pair every create/edit dialog ends with, already
    wired to the app's pill-shaped Primary/Secondary button styles."""
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Save).setText(confirm_text)
    buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("PrimaryButton")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("SecondaryButton")
    return buttons
