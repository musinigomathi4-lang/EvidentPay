"""Format validators for UPI payment evidence from multiple payment apps."""
import re
from datetime import datetime

# Accept plain numbers, Indian comma grouping and optional paise.
AMOUNT_RE = re.compile(
    r"^(?:\d+|\d{1,2}(?:,\d{2})*,\d{3}|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$"
)
UTR_RE = re.compile(r"^\d{12}$")

_MONTHS = {
    name.lower(): index
    for index, name in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        1,
    )
}
_MONTHS.update({name.lower(): index for index, name in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"], 1
)})


def is_valid_amount(text: str) -> bool:
    return bool(AMOUNT_RE.fullmatch((text or "").strip()))


def is_valid_utr(text: str) -> bool:
    return bool(UTR_RE.fullmatch((text or "").strip()))


def amount_to_int(text: str):
    """Convert an OCR amount to an integer, preserving paise when present."""
    from decimal import Decimal

    value = Decimal(str(text).replace(",", "").strip())
    return int(value) if value == value.to_integral_value() else float(value)


def _build_datetime(day, month, year, hour=None, minute=None, meridiem=None):
    try:
        day = int(day)
        month = int(month)
        year = int(year)
        if hour is None:
            return datetime(year, month, day)
        hour = int(hour)
        minute = int(minute or 0)
        if meridiem:
            marker = meridiem.lower().replace(".", "")
            hour = hour % 12 + (12 if marker == "pm" else 0)
        return datetime(year, month, day, hour, minute)
    except (TypeError, ValueError):
        return None


def parse_transaction_datetime(text: str):
    """Parse common Indian UPI receipt date/time formats.

    Supports examples such as:
      7 Sept 2026, 12:21am
      06:02 PM on 03 Oct 2026
      03/10/2026 18:02
      2026-10-03 18:02
    Numeric dates are interpreted as day/month/year.
    """
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        return None

    # Time first: '06:02 PM on 03 Oct 2026'
    time_first = re.search(
        r"(?<!\d)(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)\s+on\s+"
        r"(\d{1,2})\s+([A-Za-z]{3,9})\.?[,]?\s+(\d{4})",
        value,
        re.I,
    )
    if time_first:
        hh, mm, ap, day, mon, year = time_first.groups()
        month = _MONTHS.get(mon.lower()) or _MONTHS.get(mon[:3].lower())
        if month:
            parsed = _build_datetime(day, month, year, hh, mm, ap)
            if parsed:
                return parsed

    # Date first with 12-hour or 24-hour time.
    month_first = re.search(
        r"(?<!\d)(\d{1,2})\s+([A-Za-z]{3,9})\.?[,]?\s+(\d{4})"
        r"(?:\s*[,|]?\s*(?:at\s*)?(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?)?",
        value,
        re.I,
    )
    if month_first:
        day, mon, year, hh, mm, ap = month_first.groups()
        month = _MONTHS.get(mon.lower()) or _MONTHS.get(mon[:3].lower())
        if month:
            parsed = _build_datetime(day, month, year, hh, mm, ap)
            if parsed:
                return parsed

    # Numeric dates: DD/MM/YYYY or DD-MM-YYYY, optionally with time.
    numeric = re.search(
        r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{4})"
        r"(?:[ T,]+(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?)?",
        value,
        re.I,
    )
    if numeric:
        day, month, year, hh, mm, ap = numeric.groups()
        parsed = _build_datetime(day, month, year, hh, mm, ap)
        if parsed:
            return parsed

    # ISO-style YYYY-MM-DD, optionally with 24-hour time.
    iso = re.search(
        r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})"
        r"(?:[ T](\d{1,2}):(\d{2}))?",
        value,
    )
    if iso:
        year, month, day, hh, mm = iso.groups()
        parsed = _build_datetime(day, month, year, hh, mm)
        if parsed:
            return parsed

    return None


# Backwards-compatible name used by the existing OCR evaluation script.
def parse_gpay_date(text: str):
    return parse_transaction_datetime(text)
