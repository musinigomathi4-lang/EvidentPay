"""OCR pipeline for Google Pay 'received payment' screenshots.

Full page: PSM 4 (UTR, date, status). Amount: separate crop with the rupee glyph removed,
read at several sizes and voted, because Tesseract misreads the rupee symbol (as 2, %, *)
and is scale-sensitive on large glyphs.
"""
import os
import re
import shutil

import cv2
import pytesseract

from .image_service import load_image, amount_digits_image
from ..utils.validators import (
    AMOUNT_RE, is_valid_utr, amount_to_int, parse_gpay_date,
)

# Tesseract location: env var > Windows default > whatever is on PATH
_WIN_DEFAULT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_cmd = os.environ.get("TESSERACT_CMD") or (
    _WIN_DEFAULT if os.path.exists(_WIN_DEFAULT) else shutil.which("tesseract")
)
if _cmd:
    pytesseract.pytesseract.tesseract_cmd = _cmd

DIGIT_HEIGHTS = (28, 32, 36, 40, 44, 48, 52)


def extract_amount(img) -> dict:
    digits, flags = amount_digits_image(img)
    if digits is None:
        return {"amount": None, "amount_text": None, "flags": flags}

    votes = {}
    for h in DIGIT_HEIGHTS:
        r = h / digits.shape[0]
        im = cv2.resize(digits, None, fx=r, fy=r, interpolation=cv2.INTER_AREA)
        im = cv2.copyMakeBorder(im, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
        t = pytesseract.image_to_string(
            im, config="--psm 7 -c tessedit_char_whitelist=0123456789,").strip()
        if AMOUNT_RE.match(t):
            votes[t] = votes.get(t, 0) + 1
    if not votes:
        return {"amount": None, "amount_text": None, "flags": flags + ["no_valid_amount_reading"]}

    text = max(votes, key=votes.get)
    if votes[text] < len(DIGIT_HEIGHTS):
        flags = flags + [f"amount_scale_disagreement {votes}"]
    return {"amount": amount_to_int(text), "amount_text": text, "flags": flags}


def _mean_confidence(img) -> float:
    d = pytesseract.image_to_data(img, config="--psm 4", output_type=pytesseract.Output.DICT)
    confs = [float(c) for c, t in zip(d["conf"], d["text"]) if str(t).strip() and float(c) >= 0]
    return round(sum(confs) / len(confs), 2) if confs else 0.0


def extract_text_fields(img) -> dict:
    text = pytesseract.image_to_string(img, config="--psm 4")
    flags = []

    m = re.search(r"UPI\s+transaction\s+ID\s*\n*\s*(\d{12})\b", text, re.I)
    utr = m.group(1) if m else None
    if utr is None:
        flags.append("utr_not_found")  # no fallback guessing: UTR is the dedupe key

    dt = parse_gpay_date(text)
    if dt is None:
        flags.append("date_not_found")

    return {
        "utr": utr,
        "date": dt.strftime("%Y-%m-%d %H:%M") if dt else None,
        "status": "Completed" if re.search(r"Completed", text, re.I) else None,
        "raw_text": text,
        "confidence": _mean_confidence(img),
        "flags": flags,
    }


def extract_payment(path) -> dict:
    img = load_image(path)
    amt = extract_amount(img)
    txt = extract_text_fields(img)
    flags = amt["flags"] + txt["flags"]
    if txt["utr"] and not is_valid_utr(txt["utr"]):
        flags.append("utr_invalid")
    return {
        "amount": amt["amount"],
        "utr": txt["utr"],
        "date": txt["date"],
        "status": txt["status"],
        "raw_text": txt["raw_text"],      # original OCR text, kept for the review page
        "confidence": txt["confidence"],  # mean word confidence of the full-page read
        "flags": flags,
        "needs_review": bool(flags) or txt["status"] is None,
    }