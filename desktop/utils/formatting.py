"""Small display-formatting helpers shared across list/detail screens —
distinct from `masks.py` (live input reformatting): these only turn raw API
values into the Brazilian-friendly text the UI shows.
"""


def format_datetime_br(iso_value: str) -> str:
    """`"2026-09-04T08:00:00"` -> `"04/09/2026 08:00"`.

    Every form field in the app already shows dates as dd/MM/yyyy
    (`QDateEdit`'s `displayFormat`) — table cells were quietly falling back
    to a raw ISO slice (`yyyy-MM-dd HH:mm`) instead, the one place in the
    app that didn't match the Brazilian convention used everywhere else.
    """
    date_part, _, time_part = iso_value.partition("T")
    year, month, day = date_part.split("-")
    return f"{day}/{month}/{year} {time_part[:5]}"


def format_file_size(size_bytes: int) -> str:
    """`92631` -> `"90.5 KB"`, `1_048_576` -> `"1.0 MB"`."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def format_duration_minutes(total_minutes: int | float | None) -> str:
    """`150` -> `"2h 30min"`, `60` -> `"1h"`, `45` -> `"45 min"`."""
    if not total_minutes:
        return "—"
    hours, minutes = divmod(int(total_minutes), 60)
    if hours and minutes:
        return f"{hours}h {minutes}min"
    if hours:
        return f"{hours}h"
    return f"{minutes} min"
