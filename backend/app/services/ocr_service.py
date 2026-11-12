
"""OCR pipeline for UPI payment screenshots.

Extracts payment details from screenshots.
OCR extracts evidence; matching_service makes reconciliation decisions.
"""

import os
import re
import shutil

import cv2
import pytesseract

from .image_service import load_image, amount_digits_image
from ..utils.helpers import extract_labeled_utr
from ..utils.validators import (
    AMOUNT_RE,
    is_valid_utr,
    amount_to_int,
    parse_gpay_date,
)

# Tesseract location: environment variable > Windows default > PATH
_WIN_DEFAULT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_cmd = os.environ.get("TESSERACT_CMD") or (
    _WIN_DEFAULT if os.path.exists(_WIN_DEFAULT) else shutil.which("tesseract")
)

if _cmd:
    pytesseract.pytesseract.tesseract_cmd = _cmd


DIGIT_HEIGHTS = (28, 32, 36, 40, 44, 48, 52)


def _clean_name(value):
    """Clean OCR whitespace without guessing or correcting characters."""
    if not value:
        return None

    value = re.sub(r"\s+", " ", value).strip()
    value = value.strip(" :|-")

    return value or None


def _extract_contact_name(text):
    """Extract the contact/header name from 'From NAME'."""
    match = re.search(
        r"^\s*From\s+(?!:)([^\n]+)",
        text,
        re.I | re.M,
    )

    return _clean_name(match.group(1)) if match else None


def _extract_sender_name(text):
    """Extract the transaction-detail sender name from 'From: NAME'."""
    match = re.search(
        r"^\s*From\s*:\s*(.+)$",
        text,
        re.I | re.M,
    )

    if not match:
        return None

    # Bank details may appear in parentheses after the name.
    name = re.split(r"\s*\(", match.group(1), maxsplit=1)[0]

    return _clean_name(name)


def _extract_payment_app(text):
    """Extract the payment app mentioned in transaction details."""
    match = re.search(
        r"\bon\s+(Google\s+Pay|PhonePe|Paytm|BHIM)\b",
        text,
        re.I,
    )

    if not match:
        return None

    app = re.sub(r"\s+", " ", match.group(1)).strip()

    # Consistent display names
    known_apps = {
        "google pay": "Google Pay",
        "phonepe": "PhonePe",
        "paytm": "Paytm",
        "bhim": "BHIM",
    }

    return known_apps.get(app.lower(), app)


def _extract_status(text):
    """Recognize common payment status labels."""
    if re.search(r"\bcompleted\b|\bsuccessful\b|\bsuccess\b", text, re.I):
        return "Completed"

    if re.search(r"\bfailed\b|\bdeclined\b", text, re.I):
        return "Failed"

    if re.search(r"\bpending\b", text, re.I):
        return "Pending"

    if re.search(r"\bprocessing\b|\bin progress\b", text, re.I):
        return "Processing"

    return None


def extract_amount(img):
    """Extract amount using multiple image scales and majority voting."""
    digits, flags = amount_digits_image(img)

    if digits is None:
        return {
            "amount": None,
            "amount_text": None,
            "flags": flags,
        }

    votes = {}

    for height in DIGIT_HEIGHTS:
        ratio = height / digits.shape[0]

        resized = cv2.resize(
            digits,
            None,
            fx=ratio,
            fy=ratio,
            interpolation=cv2.INTER_AREA,
        )

        resized = cv2.copyMakeBorder(
            resized,
            20,
            20,
            20,
            20,
            cv2.BORDER_CONSTANT,
            value=255,
        )

        extracted = pytesseract.image_to_string(
            resized,
            config="--psm 7 -c tessedit_char_whitelist=0123456789,",
        ).strip()

        if AMOUNT_RE.match(extracted):
            votes[extracted] = votes.get(extracted, 0) + 1

    if not votes:
        return {
            "amount": None,
            "amount_text": None,
            "flags": flags + ["no_valid_amount_reading"],
        }

    amount_text = max(votes, key=votes.get)

    if votes[amount_text] < len(DIGIT_HEIGHTS):
        flags = flags + [f"amount_scale_disagreement {votes}"]

    return {
        "amount": amount_to_int(amount_text),
        "amount_text": amount_text,
        "flags": flags,
    }


def _mean_confidence(img):
    """Calculate average confidence of recognized OCR words."""
    data = pytesseract.image_to_data(
        img,
        config="--psm 4",
        output_type=pytesseract.Output.DICT,
    )

    confidences = []

    for confidence, word in zip(data["conf"], data["text"]):
        if not str(word).strip():
            continue

        try:
            value = float(confidence)
        except (TypeError, ValueError):
            continue

        if value >= 0:
            confidences.append(value)

    return round(sum(confidences) / len(confidences), 2) if confidences else 0.0


def extract_text_fields(img):
    """Extract text-based payment fields from the full screenshot."""
    text = pytesseract.image_to_string(img, config="--psm 4")

    flags = []

    # UTR: recover the 12-digit reference next to common UPI/reference labels.
    utr = extract_labeled_utr(text)

    if utr is None:
        compact_text = re.sub(r"[ \t]+", " ", text)
        utr_label = re.search(
            r"(?:UPI\s*)?(?:transaction\s*)?(?:ID|reference|ref(?:erence)?\s*no)"
            r"\s*[:#-]?\s*",
            compact_text,
            re.I,
        )
        if utr_label:
            utr = extract_utr(compact_text[utr_label.end():utr_label.end() + 120])

    if utr is None:
        flags.append("utr_not_found")

    # Transaction date and time.
    transaction_datetime = parse_gpay_date(text)

    if transaction_datetime is None:
        flags.append("date_not_found")

    # Separate the contact/header name from the actual sender detail.
    contact_name = _extract_contact_name(text)
    sender_name = _extract_sender_name(text)

    if contact_name is None:
        flags.append("contact_name_not_found")

    if sender_name is None:
        flags.append("sender_name_not_found")

    # Payment app.
    payment_app = _extract_payment_app(text)

    if payment_app is None:
        flags.append("payment_app_not_found")

    # Payment status.
    status = _extract_status(text)

    if status is None:
        flags.append("status_not_found")
    elif status != "Completed":
        flags.append("payment_status_not_completed")

    return {
        "utr": utr,

        # Backward-compatible field.
        "date": (
            transaction_datetime.strftime("%Y-%m-%d %H:%M")
            if transaction_datetime else None
        ),

        "transaction_date": (
            transaction_datetime.strftime("%Y-%m-%d")
            if transaction_datetime else None
        ),

        "transaction_time": (
            transaction_datetime.strftime("%H:%M")
            if transaction_datetime else None
        ),

        "sender_name": sender_name,
        "contact_name": contact_name,
        "payment_app": payment_app,

        "status": status,
        "raw_text": text,
        "confidence": _mean_confidence(img),
        "flags": flags,
    }


def extract_payment(path):
    """Run the complete OCR extraction pipeline on one screenshot."""
    try:
        img = load_image(path)
    except (FileNotFoundError, cv2.error):
        return {
            "amount": None,
            "amount_text": None,
            "utr": None,
            "date": None,
            "transaction_date": None,
            "transaction_time": None,
            "sender_name": None,
            "contact_name": None,
            "payment_app": None,
            "status": None,
            "raw_text": "",
            "confidence": 0.0,
            "flags": ["unreadable_image"],
            "needs_review": True,
        }

    amount_data = extract_amount(img)
    text_data = extract_text_fields(img)

    flags = amount_data["flags"] + text_data["flags"]

    if text_data["utr"] and not is_valid_utr(text_data["utr"]):
        flags.append("utr_invalid")

    return {
        "amount": amount_data["amount"],
        "amount_text": amount_data["amount_text"],

        "utr": text_data["utr"],
        "date": text_data["date"],
        "transaction_date": text_data["transaction_date"],
        "transaction_time": text_data["transaction_time"],

        "sender_name": text_data["sender_name"],
        "contact_name": text_data["contact_name"],
        "payment_app": text_data["payment_app"],

        "status": text_data["status"],
        "raw_text": text_data["raw_text"],
        "confidence": text_data["confidence"],

        "flags": flags,
        "needs_review": bool(flags),
    }
