"""Format validators for payment fields extracted from Google Pay screenshots."""
import re
from datetime import datetime

# Indian grouping: 0-999, or 1-2 digits then (,dd)* then ,ddd  (5,000 / 12,500 / 1,25,000)
AMOUNT_RE = re.compile(r"^(\d{1,3}|\d{1,2}(,\d{2})*,\d{3})$")
UTR_RE = re.compile(r"^\d{12}$")  # keep UTRs as strings: some start with 0

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DATE_RE = re.compile(
    r"(\d{1,2})\s+([A-Za-z]{3,4})\s+(\d{4}),?\s+(\d{1,2}):(\d{2})\s?([ap]m)", re.I)


def is_valid_amount(text: str) -> bool:
    return bool(AMOUNT_RE.match(text or ""))


def is_valid_utr(text: str) -> bool:
    return bool(UTR_RE.match(text or ""))


def amount_to_int(text: str) -> int:
    return int(text.replace(",", ""))


def parse_gpay_date(text: str):
    """'22 Sept 2026, 2:11pm' / '17 Jul 2026, 7:58 pm' -> datetime, or None."""
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    day, mon, year, hh, mm, ap = m.groups()
    month = _MONTHS.get(mon[:3].lower())  # handles 'Sept'
    if not month:
        return None
    hour = int(hh) % 12 + (12 if ap.lower() == "pm" else 0)
    try:
        return datetime(int(year), month, int(day), hour, int(mm))
    except ValueError:
        return None