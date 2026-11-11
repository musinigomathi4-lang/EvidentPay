"""General-purpose OCR pipeline for UPI payment screenshots."""

import os
import re
import shutil

import cv2
import pytesseract

from .image_service import load_image, amount_digits_image
from ..utils.helpers import (
    extract_currency_amount,
    extract_date_from_text,
    extract_utr,
)
from ..utils.validators import (
    is_valid_utr,
    amount_to_int,
)


_WIN_DEFAULT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_cmd = os.environ.get("TESSERACT_CMD") or (
    _WIN_DEFAULT
    if os.path.exists(_WIN_DEFAULT)
    else shutil.which("tesseract")
)

if _cmd:
    pytesseract.pytesseract.tesseract_cmd = _cmd


DIGIT_HEIGHTS = (28, 32, 36, 40, 44, 48, 52)


def _clean_name(value):
    if not value:
        return None

    value = re.sub(r"\s+", " ", value).strip()
    value = value.strip(" :|-")

    return value or None


def _extract_contact_name(text):
    """
    Supports common patterns such as:

    From NAME
    Paid to NAME
    Sent to NAME
    To NAME
    """

    patterns = (
        r"^\s*From\s+(?!:)([^\n]+)",
        r"^\s*Paid\s+to\s+([^\n]+)",
        r"^\s*Sent\s+to\s+([^\n]+)",
        r"^\s*To\s+([^\n]+)",
    )

    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)

        if match:
            return _clean_name(match.group(1))

    return None


def _extract_sender_name(text):
    """
    Extract transaction-detail sender names.

    Supports:
        From: NAME
        From NAME
        Received from NAME
        Paid by NAME
        Sent by NAME
    """

    patterns = (
        r"^\s*From\s*:\s*(.+)$",
        r"^\s*Received\s+from\s+(.+)$",
        r"^\s*Paid\s+by\s+(.+)$",
        r"^\s*Sent\s+by\s+(.+)$",
    )

    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)

        if not match:
            continue

        name = match.group(1)

        # Remove bank/account information after parentheses.
        name = re.split(r"\s*\(", name, maxsplit=1)[0]

        # Remove common trailing labels.
        name = re.split(
            r"\s+(?:via|on|using)\s+",
            name,
            maxsplit=1,
            flags=re.I,
        )[0]

        return _clean_name(name)

    return None


def _extract_payment_app(text):
    pattern = re.search(
        r"\b(?:on|via|using)\s+"
        r"(Google\s+Pay|GooglePay|PhonePe|Paytm|BHIM)\b",
        text,
        re.I,
    )

    if not pattern:
        return None

    value = re.sub(r"\s+", " ", pattern.group(1)).strip()

    mapping = {
        "googlepay": "Google Pay",
        "google pay": "Google Pay",
        "phonepe": "PhonePe",
        "paytm": "Paytm",
        "bhim": "BHIM",
    }

    return mapping.get(value.lower(), value)


def _extract_status(text):
    if re.search(
        r"\bcompleted\b|\bsuccessful\b|\bsuccess\b|\bpaid\b",
        text,
        re.I,
    ):
        return "Completed"

    if re.search(
        r"\bfailed\b|\bdeclined\b|\breversed\b",
        text,
        re.I,
    ):
        return "Failed"

    if re.search(r"\bpending\b", text, re.I):
        return "Pending"

    if re.search(
        r"\bprocessing\b|\bin progress\b",
        text,
        re.I,
    ):
        return "Processing"

    return None


def _mean_confidence(img):
    data = pytesseract.image_to_data(
        img,
        config="--psm 4",
        output_type=pytesseract.Output.DICT,
    )

    confidences = []

    for confidence, word in zip(
        data["conf"],
        data["text"],
    ):
        if not str(word).strip():
            continue

        try:
            value = float(confidence)
        except (TypeError, ValueError):
            continue

        if value >= 0:
            confidences.append(value)

    return (
        round(sum(confidences) / len(confidences), 2)
        if confidences
        else 0.0
    )


def _extract_amount_from_image(img):
    """
    Existing visual amount extraction remains the preferred method.
    """

    digits, flags = amount_digits_image(img)

    if digits is None:
        return None, flags

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
            config="--psm 7 -c tessedit_char_whitelist=0123456789,.",
        ).strip()

        # Only accept plausible amount strings.
        if re.fullmatch(
            r"\d{1,3}(?:,\d{2})*,\d{3}(?:\.\d{1,2})?"
            r"|\d+(?:\.\d{1,2})?",
            extracted,
        ):
            votes[extracted] = votes.get(extracted, 0) + 1

    if not votes:
        return None, flags + ["no_valid_amount_reading"]

    amount_text = max(votes, key=votes.get)

    if votes[amount_text] < len(DIGIT_HEIGHTS):
        flags = flags + [f"amount_scale_disagreement {votes}"]

    try:
        amount = int(amount_text.replace(",", "").split(".")[0])
    except ValueError:
        return None, flags + ["amount_conversion_failed"]

    return amount, flags


def extract_text_fields(img):
    """
    Extract all text-based fields from the screenshot.

    The OCR text is treated as evidence. It is never used to
    automatically declare a payment genuine.
    """

    # Run more than one OCR segmentation mode because screenshots
    # can have different layouts.
    text_psm4 = pytesseract.image_to_string(
        img,
        config="--psm 4",
    )

    text_psm6 = pytesseract.image_to_string(
        img,
        config="--psm 6",
    )

    text = text_psm4

    # If psm 4 produced very little text, use psm 6.
    if len(text.strip()) < 20:
        text = text_psm6

    flags = []

    utr = extract_utr(text)

    if utr is None:
        flags.append("utr_not_found")

    transaction_datetime = extract_date_from_text(text)

    if transaction_datetime is None:
        flags.append("date_not_found")

    contact_name = _extract_contact_name(text)
    sender_name = _extract_sender_name(text)

    if contact_name is None:
        flags.append("contact_name_not_found")

    if sender_name is None:
        flags.append("sender_name_not_found")

    payment_app = _extract_payment_app(text)

    if payment_app is None:
        flags.append("payment_app_not_found")

    status = _extract_status(text)

    if status is None:
        flags.append("status_not_found")

    elif status != "Completed":
        flags.append("payment_status_not_completed")

    return {
        "utr": utr,

        "date": (
            transaction_datetime.strftime("%Y-%m-%d %H:%M")
            if transaction_datetime
            else None
        ),

        "transaction_date": (
            transaction_datetime.strftime("%Y-%m-%d")
            if transaction_datetime
            else None
        ),

        "transaction_time": (
            transaction_datetime.strftime("%H:%M")
            if transaction_datetime
            else None
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
    """
    Run the complete generalized OCR extraction pipeline.
    """

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

    flags = []

    # --------------------------------------------------
    # 1. OCR text
    # --------------------------------------------------

    text_data = extract_text_fields(img)

    flags.extend(text_data["flags"])

    # --------------------------------------------------
    # 2. Amount from visual crop
    # --------------------------------------------------

    amount, amount_flags = _extract_amount_from_image(img)

    flags.extend(amount_flags)

    # --------------------------------------------------
    # 3. Amount fallback from OCR text
    # --------------------------------------------------

    if amount is None:
        fallback_amount = extract_currency_amount(
            text_data["raw_text"]
        )

        if fallback_amount is not None:
            amount = int(fallback_amount)
            flags.append("amount_from_text_fallback")

    if amount is None:
        flags.append("amount_not_found")

    # --------------------------------------------------
    # 4. Validate UTR
    # --------------------------------------------------

    if text_data["utr"] and not is_valid_utr(text_data["utr"]):
        flags.append("utr_invalid")

    # --------------------------------------------------
    # 5. Return normalized result
    # --------------------------------------------------

    return {
        "amount": amount,

        "amount_text": (
            str(amount)
            if amount is not None
            else None
        ),

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