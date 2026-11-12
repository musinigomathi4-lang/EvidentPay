"""Reusable helpers for flexible payment and bank-statement parsing."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


_DATE_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",

    "%d-%m-%Y %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y",

    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",

    "%d-%b-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d %b, %Y",

    "%d-%m-%y",
    "%d/%m/%y",

    "%d.%m.%Y",
    "%d.%m.%y",
)


# Standalone 12-digit UPI UTR/reference number.
UTR_RE = re.compile(r"(?<!\d)(\d{12})(?!\d)")


def parse_date(value):
    """
    Parse common Indian/UPI/bank date formats.

    Returns datetime or None.
    """

    if isinstance(value, datetime):
        return value

    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)

    s = str(value or "").strip()

    if not s:
        return None

    # Remove excessive whitespace.
    s = re.sub(r"\s+", " ", s)

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass

    return None


def parse_amount(value):
    """
    Parse common Indian currency representations.

    Examples:
        ₹5,000
        Rs. 500
        INR 500.00
        500
        1,25,000
        500.00
    """

    if isinstance(value, Decimal):
        return value

    if isinstance(value, int):
        return Decimal(value)

    if isinstance(value, float):
        return Decimal(str(value))

    s = str(value or "").strip()

    if not s:
        return None

    # Remove currency labels/symbols.
    s = re.sub(r"(?i)\b(?:inr|rs|rs\.)\b", "", s)
    s = s.replace("₹", "")
    s = s.replace("$", "")
    s = s.replace(" ", "")

    # Keep digits, commas and decimal point.
    s = re.sub(r"[^\d.,]", "", s)

    if not s:
        return None

    # Indian comma grouping.
    if "," in s and "." not in s:
        s = s.replace(",", "")

    # If both exist, commas are thousands separators.
    elif "," in s and "." in s:
        s = s.replace(",", "")

    # Handle accidental multiple decimal points conservatively.
    if s.count(".") > 1:
        parts = s.split(".")
        s = parts[0] + "." + "".join(parts[1:])

    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def normalize_utr(value):
    """Normalize a 12-digit UTR, preserving leading zeroes."""
    if value is None:
        return None
    digits = re.sub(r"[\s-]", "", str(value).strip())
    return digits if re.fullmatch(r"\d{12}", digits) else None


def extract_utr(*texts):
<<<<<<< HEAD
    """
    Extract a 12-digit UPI/reference number from any supplied text.

    Does not invent or modify digits.
    """

    # First prefer values appearing after a UTR/reference label.
    labelled_patterns = (
        r"(?i)(?:upi\s+transaction\s+id|transaction\s+id|"
        r"upi\s+ref(?:erence)?|utr|reference\s+(?:no|number)?|"
        r"ref(?:erence)?\s*(?:no|number)?|rrn)"
        r"\s*[:#\-]?\s*([0-9]{12})(?!\d)",
    )

    combined = "\n".join(str(t or "") for t in texts)

    for pattern in labelled_patterns:
        match = re.search(pattern, combined)
        if match:
            return match.group(1)

    # Fall back to any standalone 12-digit number.
    for text in texts:
        match = UTR_RE.search(str(text or ""))
        if match:
            return match.group(1)

    return None


def extract_date_from_text(text):
    """
    Find a recognizable date anywhere inside OCR/text output.
    """

    text = str(text or "")

    patterns = (
        # 22 Sept 2026, 2:11pm
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4},?\s+\d{1,2}:\d{2}\s*[ap]m\b",

        # 22 Sept 2026
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b",

        # 22/09/2026 or 22-09-2026 or 22.09.2026
        r"\b\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}\b",

        # 2026-09-22
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
    )

    for pattern in patterns:
        match = re.search(pattern, text, re.I)

        if match:
            candidate = match.group(0)

            # Try the exact candidate first.
            parsed = parse_date(candidate)

            if parsed:
                return parsed

            # GPay-style date/time.
            gpay = re.match(
                r"(?i)(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4}),?\s+"
                r"(\d{1,2}):(\d{2})\s*([ap]m)",
                candidate,
            )

            if gpay:
                day, month_name, year, hour, minute, ampm = gpay.groups()

                month_lookup = {
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

                month = month_lookup.get(month_name[:4].lower())

                if month:
                    hour = int(hour) % 12
                    if ampm.lower() == "pm":
                        hour += 12

                    try:
                        return datetime(
                            int(year),
                            month,
                            int(day),
                            hour,
                            int(minute),
                        )
                    except ValueError:
                        pass

    return None


def extract_currency_amount(text):
    """
    Find an amount that is explicitly associated with currency.

    This is used as a fallback when the visual amount crop is unreliable.
    """

    text = str(text or "")

    patterns = (
        r"(?i)(?:₹|rs\.?|inr)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        r"(?i)([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:₹|rs\.?|inr)\b",
        r"(?i)(?:amount|paid|payment|total)\s*[:\-]?\s*"
        r"(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    )

    candidates = []

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            amount = parse_amount(match.group(1))

            if amount is not None:
                candidates.append(amount)

    if not candidates:
        return None

    # Prefer the first explicit currency amount rather than arbitrary
    # 12-digit IDs or dates.
    return candidates[0]
=======
    """Extract a 12-digit UTR from statement fields/descriptions."""
    for value in texts:
        raw = str(value or "").strip()
        if not raw:
            continue
        match = _UTR_RE.search(raw)
        if match:
            return match.group()
        match = re.search(r"(?<!\d)(?:\d[ \t\r\n-]*){11}\d(?!\d)", raw)
        if match:
            digits = re.sub(r"\D", "", match.group())
            if len(digits) == 12:
                return digits
    return None


def extract_labeled_utr(text):
    """Find a UTR near a UPI/reference label in OCR text."""
    raw = str(text or "")
    label = re.search(
        r"(?:UPI\s*)?(?:transaction\s*)?(?:ID|reference|ref(?:erence)?\s*no)"
        r"\s*[:#-]?\s*",
        raw,
        re.I,
    )
    if label:
        found = extract_utr(raw[label.end():label.end() + 160])
        if found:
            return found
    compact = re.sub(r"[ \t]+", " ", raw)
    label = re.search(
        r"(?:UPI\s*)?(?:transaction\s*)?(?:ID|reference|ref(?:erence)?\s*no)"
        r"\s*[:#-]?\s*",
        compact,
        re.I,
    )
    return extract_utr(compact[label.end():label.end() + 160]) if label else None
>>>>>>> 32d0f17ba771021b201aa7c909e282366f9b892c


def hamming(a: str, b: str) -> int:
    """Number of differing positions between equal-length strings."""

    if len(a) != len(b):
        return 10 ** 6

    return sum(x != y for x, y in zip(a, b))