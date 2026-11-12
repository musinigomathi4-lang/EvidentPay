"""Small reusable helpers: flexible date/amount parsing and UTR extraction."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# Day-first (Indian) formats. '02-06-2026' means 2 June, never 6 February.
_DATE_FORMATS = (
    "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
    "%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y",
    "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y",
    "%d-%b-%Y", "%d %b %Y", "%d %B %Y", "%d %b, %Y", "%d-%m-%y", "%d/%m/%y",
)
_UTR_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")


def parse_date(value):
    """Return a datetime, or None. Accepts datetime/date objects and common string formats."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    s = str(value or "").strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def parse_amount(value):
    """'₹5,000' / 'Rs. 500.00' / 500 -> Decimal; blank, '-' or junk -> None."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    s = re.sub(r"[^\d.]", "", str(value or ""))
    if not s or s == ".":
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def extract_utr(*texts):
    """First standalone 12-digit number in the given strings (UTRs are text, never int)."""
    for t in texts:
        m = _UTR_RE.search(str(t or ""))
        if m:
            return m.group()
    return None


def hamming(a: str, b: str) -> int:
    """Number of differing positions between two equal-length strings (else a large number)."""
    if len(a) != len(b):
        return 10 ** 6
    return sum(x != y for x, y in zip(a, b))