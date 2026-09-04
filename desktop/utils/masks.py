"""Real-time input formatting for Brazilian CPF, CNPJ and phone fields.

Qt's native `QLineEdit.setInputMask()` handles a fixed-length format (CPF,
CNPJ) fine, but can't express a phone number's two valid lengths (10-digit
landline vs. 11-digit mobile) — so every field here goes through the same
lightweight `textChanged`-driven reformatter instead, so CPF/CNPJ/phone are
all formatted identically everywhere they appear, by construction.
"""
import re

from PySide6.QtWidgets import QLineEdit


def _only_digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def format_cpf(digits: str) -> str:
    digits = digits[:11]
    out = ".".join(part for part in (digits[0:3], digits[3:6], digits[6:9]) if part)
    if len(digits) > 9:
        out += f"-{digits[9:11]}"
    return out


def format_cnpj(digits: str) -> str:
    digits = digits[:14]
    out = digits[0:2]
    if len(digits) > 2:
        out += f".{digits[2:5]}"
    if len(digits) > 5:
        out += f".{digits[5:8]}"
    if len(digits) > 8:
        out += f"/{digits[8:12]}"
    if len(digits) > 12:
        out += f"-{digits[12:14]}"
    return out


def format_phone(digits: str) -> str:
    """`(11) 3456-7890` (landline, 10 digits) or `(11) 98888-1111` (mobile, 11)."""
    digits = digits[:11]
    if not digits:
        return ""
    out = f"({digits[0:2]}"
    if len(digits) > 2:
        out += ") "
    remaining = digits[2:]
    if len(remaining) <= 4:
        out += remaining
    elif len(remaining) <= 8:
        out += f"{remaining[:4]}-{remaining[4:]}"
    else:
        out += f"{remaining[:5]}-{remaining[5:9]}"
    return out


def bind_live_format(line_edit: QLineEdit, formatter) -> None:
    """Reformat `line_edit` on every keystroke with `formatter` (one of the
    `format_*` functions above), keeping the cursor after the same digit it
    was after before the reformat — not just parked at the end — so editing
    in the middle of an already-filled field stays usable.
    """

    def _on_text_changed(text: str) -> None:
        digits = _only_digits(text)
        formatted = formatter(digits)
        if formatted == text:
            return
        digits_before_cursor = len(_only_digits(text[: line_edit.cursorPosition()]))
        line_edit.blockSignals(True)
        line_edit.setText(formatted)
        new_pos, seen_digits = 0, 0
        for index, char in enumerate(formatted):
            if seen_digits >= digits_before_cursor:
                break
            if char.isdigit():
                seen_digits += 1
            new_pos = index + 1
        line_edit.setCursorPosition(new_pos)
        line_edit.blockSignals(False)

    line_edit.textChanged.connect(_on_text_changed)
