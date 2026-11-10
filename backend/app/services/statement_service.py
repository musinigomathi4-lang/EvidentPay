
"""Normalize CSV and text-based PDF bank statements."""

import csv
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pdfplumber

from ..utils.helpers import parse_date, parse_amount, extract_utr


def _find(header, *needles, exclude=()):
    for h in header:
        low = str(h or "").lower().replace("_", " ")
        if any(n in low for n in needles) and not any(x in low for x in exclude):
            return h
    return None


def _normalize_rows(rows):
    if not rows:
        return []

    header = [str(value or "").strip() for value in rows[0]]

    c_date = (
        _find(header, "txn date", "transaction date", "value date", "posting date")
        or _find(header, "date")
    )
    c_utr = _find(header, "utr", "reference", "ref no", "ref.", "ref")
    c_desc = _find(header, "description", "narration", "particulars", "remarks", "details")
    c_credit = _find(header, "credit", "deposit", "cr amount", "received")
    c_debit = _find(header, "debit", "withdrawal", "dr amount", "paid")
    c_amount = _find(header, "amount", exclude=("credit", "debit"))
    c_type = _find(header, "type", "dr/cr", "cr/dr")

    if not any((c_date, c_utr, c_desc, c_credit, c_debit, c_amount)):
        return []

    indexes = {name: header.index(name) for name in header if name is not None}

    def cell(row, column):
        if column is None:
            return None
        try:
            return row[indexes[column]]
        except (IndexError, KeyError):
            return None

    txns = []

    for row_number, row in enumerate(rows[1:], start=1):
        if not row or not any(str(value or "").strip() for value in row):
            continue

        desc = str(cell(row, c_desc) or "").strip()
        credit = parse_amount(cell(row, c_credit)) if c_credit else None
        debit = parse_amount(cell(row, c_debit)) if c_debit else None

        if credit is None and debit is None and c_amount:
            amount = parse_amount(cell(row, c_amount))
            kind = str(cell(row, c_type) or "").strip().lower()

            if amount is not None:
                if kind.startswith(("cr", "credit")):
                    credit = amount
                elif kind.startswith(("dr", "debit")):
                    debit = amount

        txns.append({
            "row": row_number,
            "date": parse_date(cell(row, c_date)) if c_date else None,
            "utr": extract_utr(cell(row, c_utr) if c_utr else None, desc),
            "credit": credit or Decimal(0),
            "debit": debit or Decimal(0),
            "description": desc,
        })

    return txns


def load_statement_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as file:
        rows = list(csv.reader(file))

    return _normalize_rows(rows)


def _extract_date_time(value):
    """Parse dates such as 01Apr,2026 07:37PM."""
    value = re.sub(r"\s+", " ", value.strip())

    formats = (
        "%d%b,%Y %I:%M%p",
        "%d %b,%Y %I:%M%p",
        "%d%b, %Y %I:%M%p",
        "%d %b, %Y %I:%M%p",
        "%d-%b-%Y %I:%M%p",
        "%d/%m/%Y %I:%M%p",
    )

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return parse_date(value)


def _extract_pdf_text_transactions(text):
    """Extract transaction rows from positioned PDF text."""

    # Flatten line breaks while preserving transaction boundaries by date.
    text = re.sub(r"\s+", " ", text).strip()

    date_pattern = re.compile(
        r"(?<!\d)"
        r"(\d{1,2}\s*[A-Za-z]{3},\s*\d{4}\s+"
        r"\d{1,2}:\d{2}\s*(?:AM|PM))"
        r"\b",
        re.IGNORECASE,
    )

    matches = list(date_pattern.finditer(text))

    if not matches:
        return []

    amount_pattern = re.compile(
        r"(?:₹|Rs\.?\s*)\s*([\d,]+(?:\.\d{1,2})?)\s*$",
        re.IGNORECASE,
    )

    transactions = []

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)

        segment = text[start:end].strip()
        date_text = match.group(1)

        transaction_date = _extract_date_time(date_text)

        if transaction_date is None:
            continue

        details = segment[match.end() - start:].strip()

        amount_match = amount_pattern.search(details)

        if not amount_match:
            # Fallback for PDFs that omit the currency symbol.
            amount_match = re.search(
                r"([\d,]+(?:\.\d{1,2})?)\s*$",
                details,
            )

        if not amount_match:
            continue

        amount = parse_amount(amount_match.group(1))

        if amount is None:
            continue

        description = details[:amount_match.start()].strip()

        # This statement format uses "Received from" for incoming credits.
        # "Paid to HDFC Bank" may describe the destination bank, so do not
        # classify that phrase alone as an outgoing debit.
        normalized_description = re.sub(
            r"(?i)receivedfrom",
            "received from",
            description,
        ).lower()

        if "received from" in normalized_description or "credited" in normalized_description:
            credit = amount
            debit = Decimal(0)
        elif "debited" in normalized_description or normalized_description.startswith("paid to"):
            credit = Decimal(0)
            debit = amount
        else:
            # Unknown transaction direction should not be guessed.
            credit = Decimal(0)
            debit = Decimal(0)

        transactions.append({
            "row": len(transactions) + 1,
            "date": transaction_date,
            "utr": extract_utr(description),
            "credit": credit,
            "debit": debit,
            "description": description,
        })

    return transactions


def load_statement_pdf(path):
    extracted_tables = []
    extracted_text = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                cleaned = [
                    [str(value or "").replace("\n", " ").strip() for value in row]
                    for row in table if row
                ]

                if cleaned:
                    extracted_tables.extend(cleaned)

            page_text = page.extract_text()

            if page_text:
                extracted_text.append(page_text)

    # Preserve the existing table extraction as the first attempt.
    transactions = _normalize_rows(extracted_tables)

    if transactions:
        return transactions

    # Fallback for text-based PDFs without detectable table borders.
    transactions = _extract_pdf_text_transactions(
        "\n".join(extracted_text)
    )

    if transactions:
        return transactions

    raise ValueError(
        "Could not extract transaction rows from this PDF. "
        "It may be scanned, password-protected, or use an unsupported bank format."
    )


def statement_period(txns):
    days = [t["date"].date() for t in txns if t["date"]]

    return (min(days), max(days)) if days else (None, None)
