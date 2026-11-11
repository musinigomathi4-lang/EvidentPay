"""Validation helpers for payment fields."""

import re
from datetime import datetime


AMOUNT_RE = re.compile(
    r"^(?:\d{1,3}|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d{1,2})?$"
)

UTR_RE = re.compile(r"^\d{12}$")


def is_valid_amount(text: str) -> bool:
    return bool(AMOUNT_RE.match(str(text or "").strip()))


def is_valid_utr(text: str) -> bool:
    return bool(UTR_RE.match(str(text or "").strip()))


def amount_to_int(text: str) -> int:
    return int(str(text).replace(",", ""))


_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def parse_gpay_date(text: str):
    """
    Parse dates such as:

    22 Sept 2026, 2:11pm
    17 Jul 2026, 7:58 pm

    Returns datetime or None.
    """

    pattern = re.compile(
        r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4}),?\s+"
        r"(\d{1,2}):(\d{2})\s*([ap]m)",
        re.I,
    )

    match = pattern.search(text or "")

    if not match:
        return None

    day, mon, year, hh, mm, ap = match.groups()

    month = _MONTHS.get(mon[:4].lower())

    if not month:
        return None

    hour = int(hh) % 12

    if ap.lower() == "pm":
        hour += 12

    try:
        return datetime(
            int(year),
            month,
            int(day),
            hour,
            int(mm),
        )
    except ValueError:
        return None