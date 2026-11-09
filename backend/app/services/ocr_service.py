"""Layout-tolerant OCR pipeline for UPI payment screenshots.

Tesseract reads pixels; the parsers below interpret common receipt labels.
No training screenshot is required at runtime.
"""
import os
import re
import shutil

import cv2
import pytesseract

from .image_service import load_image, amount_digits_image
from ..utils.validators import (
    AMOUNT_RE,
    is_valid_utr,
    amount_to_int,
    parse_transaction_datetime,
)

_WIN_DEFAULT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_cmd = os.environ.get("TESSERACT_CMD") or (
    _WIN_DEFAULT if os.path.exists(_WIN_DEFAULT) else shutil.which("tesseract")
)
if _cmd:
    pytesseract.pytesseract.tesseract_cmd = _cmd

DIGIT_HEIGHTS = (32, 36, 40, 44, 48)


def _clean_name(value):
    if not value:
        return None
    value = re.sub(r"\s+", " ", value).strip(" :|-/")
    value = re.sub(r"\s+(?:UPI|IMPS|NEFT|HDFC|SBI|ICICI|AXIS|BANK)\b.*$", "", value, flags=re.I)
    value = re.split(r"\s+(?:on|via)\s+(?:Google Pay|PhonePe|Paytm|BHIM)\b", value, flags=re.I)[0]
    value = value.strip(" :|-/")
    if not value or len(value) > 100:
        return None
    # Do not report a masked phone number, VPA, or account number as a person's name.
    if re.search(r"\d{3,}|[xX*]{3,}|@|\+\s*91", value):
        return None
    if not re.search(r"[A-Za-z]{2}", value):
        return None
    if re.search(r"^(?:unknown|not available|payment|transaction|successful|completed)$", value, re.I):
        return None
    return value


def _extract_labeled_person(text, labels):
    label_pattern = "|".join(labels)
    match = re.search(
        rf"^\s*(?:{label_pattern})\s*:?\s*(.*?)\s*$",
        text or "",
        re.I | re.M,
    )
    if not match:
        return None
    candidate = match.group(1).strip()
    if not candidate:
        lines = (text or "").splitlines()
        line_index = next(
            (i for i, line in enumerate(lines)
             if re.match(rf"^\s*(?:{label_pattern})\s*:?\s*$", line, re.I)),
            None,
        )
        if line_index is not None:
            for following in lines[line_index + 1:line_index + 4]:
                following = following.strip()
                if not following:
                    continue
                if re.search(r"^(?:\+?\d|[xX*]{3,}|\+?91\b)", following):
                    return None
                candidate = following
                break
    return _clean_name(candidate)


def _extract_contact_name(text):
    """Header/contact name, commonly displayed as 'From NAME'."""
    return _extract_labeled_person(text, [r"From(?!\s*:)"])


def _extract_sender_name(text):
    """Sender name across 'From:', 'Received from', and 'Paid by' labels."""
    return _extract_labeled_person(
        text,
        [r"From", r"Received\s+from", r"Paid\s+by", r"Sent\s+by"],
    )


def _extract_utr(text):
    """Extract a 12-digit UTR without confusing app-specific transaction IDs."""
    text = text or ""
    labels = re.finditer(
        r"\b(?:UTR|UPI\s*(?:transaction\s*ID|reference(?:\s*(?:no|number))?|ref\s*(?:no|number)?))\b\s*[:#-]?",
        text,
        re.I,
    )
    for label in labels:
        window = text[label.end():label.end() + 100]
        digits = re.search(r"(?<!\d)(\d{12})(?!\d)", window.replace(" ", ""))
        if digits:
            return digits.group(1)

    # Some receipts place the UTR label on the previous OCR line.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if re.search(r"\b(?:UTR|UPI\s*(?:transaction\s*ID|reference|ref))\b", line, re.I):
            for candidate in lines[index:index + 3]:
                compact = re.sub(r"\s+", "", candidate)
                found = re.search(r"(?<!\d)(\d{12})(?!\d)", compact)
                if found:
                    return found.group(1)
    return None


def _extract_payment_app(text):
    """Prefer receipt-origin signatures over incidental recipient VPA providers."""
    value = re.sub(r"[\w.+-]+@[\w.-]+", " ", text or "")
    rules = [
        ("PhonePe", r"\bPhonePe\s+(?:Transaction|Reference|UPI)\b|\bPhonePe\s+Support\b|\bView\s+History\b"),
        ("Paytm", r"\bSent\s+using\s+Paytm\b|\bPaytm\s+UPI\b|\bPaytm\s+Transaction\s+ID\b"),
        ("Google Pay", r"\bGoogle\s+transaction\s+ID\b|\b(?:Paid|Sent|Received)\s+(?:using|via|through)\s+Google\s+Pay\b|\bGoogle\s+Pay\s+transaction\b"),
        ("BHIM", r"\bBHIM\s+(?:UPI|app|transaction)\b"),
        ("Amazon Pay", r"\bAmazon\s+Pay\s+(?:UPI|transaction|receipt)\b"),
        ("WhatsApp Pay", r"\bWhatsApp\s+Pay\b"),
        ("MobiKwik", r"\bMobiKwik\b"),
        ("Airtel Thanks", r"\bAirtel\s+Thanks\b"),
        ("Freecharge", r"\bFreecharge\b"),
    ]
    for app, pattern in rules:
        if re.search(pattern, value, re.I):
            return app

    # Recognize a standalone receipt header, but not a recipient address such as
    # '... on Google Pay' or '... on PhonePe'.
    for app, brand in (
        ("Google Pay", r"Google\s+Pay"),
        ("PhonePe", r"PhonePe"),
        ("Paytm", r"Paytm"),
        ("BHIM", r"BHIM"),
    ):
        if re.search(rf"(?<!on )\b{brand}\b", value, re.I):
            return app
    return None


def _extract_status(text):
    value = text or ""
    if re.search(r"\b(?:transaction\s+)?successful\b|\bcompleted\b|\bsuccess\b", value, re.I):
        return "Completed"
    if re.search(r"\bfailed\b|\bdeclined\b|\breversed\b", value, re.I):
        return "Failed"
    if re.search(r"\bpending\b|\bin progress\b|\bprocessing\b", value, re.I):
        return "Pending"
    return None


def _text_score(text):
    if not text:
        return 0
    labels = re.findall(
        r"\b(?:UTR|UPI|transaction|received|from|paid|amount|completed|successful|failed|PhonePe|Paytm|Google|BHIM|INR)\b",
        text,
        re.I,
    )
    return len(re.sub(r"\s", "", text)) + 24 * len(labels)


def _ocr_text(img):
    """Run a small preprocessing/PSM ensemble to tolerate light and dark themes."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    variants = [gray]

    # Upscaling helps screenshots with small text. Keep the original as a candidate.
    scale = 1.5 if max(gray.shape) < 2200 else 1.0
    if scale > 1:
        enlarged = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        variants.append(enlarged)
    else:
        enlarged = gray

    _, otsu = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.extend([otsu, 255 - otsu])

    candidates = []
    for variant in variants:
        for psm in (6, 11):
            try:
                candidate = pytesseract.image_to_string(variant, config=f"--oem 3 --psm {psm}")
            except pytesseract.TesseractError:
                continue
            candidates.append(candidate)
    if not candidates:
        return pytesseract.image_to_string(img, config="--oem 3 --psm 6")
    return max(candidates, key=_text_score)


def _amount_from_text(text):
    """Use explicit currency/amount lines as a layout-independent fallback."""
    candidates = []
    for line in (text or "").splitlines():
        clean = line.strip()
        if not clean:
            continue
        if re.search(r"UTR|transaction\s*ID|reference|\bdate\b|\btime\b|\+?91|@|account|balance|bank", clean, re.I):
            continue
        match = re.search(
            r"(?:₹|Rs\.?|INR|[*%])\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
            clean,
            re.I,
        )
        if not match:
            continue
        raw = match.group(1).replace(",", "")
        try:
            value = amount_to_int(raw)
        except (ValueError, ArithmeticError):
            continue
        # Currency marker and a short numeric value on its own line are strong evidence.
        candidates.append((value, match.group(1), len(clean)))
    if not candidates:
        return None, None
    distinct = {str(item[0]) for item in candidates}
    if len(distinct) > 1:
        return None, None
    return candidates[0][0], candidates[0][1]


def extract_amount(img, raw_text=None):
    """Extract amount using the existing visual crop, then a currency-line fallback."""
    text_amount, text_amount_display = _amount_from_text(raw_text)
    digits, flags = amount_digits_image(img)

    crop_amount = None
    crop_display = None
    if digits is not None:
        votes = {}
        for height in DIGIT_HEIGHTS:
            ratio = height / digits.shape[0]
            resized = cv2.resize(
                digits, None, fx=ratio, fy=ratio, interpolation=cv2.INTER_AREA
            )
            resized = cv2.copyMakeBorder(
                resized, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255
            )
            extracted = pytesseract.image_to_string(
                resized,
                config="--psm 7 -c tessedit_char_whitelist=0123456789,.",
            ).strip().replace(" ", "")
            if AMOUNT_RE.fullmatch(extracted):
                votes[extracted] = votes.get(extracted, 0) + 1
        if votes:
            crop_display = max(votes, key=votes.get)
            crop_amount = amount_to_int(crop_display)
            if votes[crop_display] < len(DIGIT_HEIGHTS):
                flags = flags + ["amount_scale_disagreement"]

    if text_amount is not None and crop_amount is not None and text_amount != crop_amount:
        return {
            "amount": None,
            "amount_text": None,
            "flags": flags + ["amount_conflicting_readings"],
        }

    if text_amount is not None:
        # The explicit currency-labelled text is a valid independent extraction path.
        # Do not flag a missing/unsuitable visual crop when the text path succeeded.
        return {
            "amount": text_amount,
            "amount_text": text_amount_display,
            "flags": [],
        }

    if crop_amount is not None:
        return {
            "amount": crop_amount,
            "amount_text": crop_display,
            "flags": flags,
        }

    return {
        "amount": None,
        "amount_text": None,
        "flags": flags + ["no_valid_amount_reading"],
    }


def _mean_confidence(img):
    data = pytesseract.image_to_data(
        img, config="--oem 3 --psm 6", output_type=pytesseract.Output.DICT
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
    text = _ocr_text(img)
    flags = []

    utr = _extract_utr(text)
    if utr is None:
        flags.append("utr_not_found")

    transaction_datetime = parse_transaction_datetime(text)
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
        "date": transaction_datetime.strftime("%Y-%m-%d %H:%M") if transaction_datetime else None,
        "transaction_date": transaction_datetime.strftime("%Y-%m-%d") if transaction_datetime else None,
        "transaction_time": transaction_datetime.strftime("%H:%M") if transaction_datetime else None,
        "sender_name": sender_name,
        "contact_name": contact_name,
        "payment_app": payment_app,
        "status": status,
        "raw_text": text,
        "confidence": _mean_confidence(img),
        "flags": flags,
    }


def extract_payment(path):
    try:
        img = load_image(path)
    except (FileNotFoundError, cv2.error):
        return {
            "amount": None, "amount_text": None, "utr": None, "date": None,
            "transaction_date": None, "transaction_time": None,
            "sender_name": None, "contact_name": None, "payment_app": None,
            "status": None, "raw_text": "", "confidence": 0.0,
            "flags": ["unreadable_image"], "needs_review": True,
        }

    text_data = extract_text_fields(img)
    amount_data = extract_amount(img, text_data["raw_text"])
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
