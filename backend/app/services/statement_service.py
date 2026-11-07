"""Normalize CSV and text-based PDF bank statements into one transaction shape.

PDF extraction uses table detection. Scanned/image-only PDFs need OCR and are rejected
with a clear message rather than silently importing incomplete data.
"""
import csv
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
    c_date = (_find(header, "txn date", "transaction date", "value date", "posting date")
              or _find(header, "date"))
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


def load_statement_pdf(path):
    extracted_tables = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                cleaned = [
                    [str(value or "").replace("\\n", " ").strip() for value in row]
                    for row in table if row
                ]
                if cleaned:
                    extracted_tables.extend(cleaned)

    transactions = _normalize_rows(extracted_tables)
    if not transactions:
        raise ValueError(
            "No readable transaction table was found. This PDF may be scanned, "
            "password-protected, or formatted in a way that needs a bank-specific parser. "
            "Try exporting it as CSV or provide a text-based PDF statement."
        )
    return transactions


def statement_period(txns):
    days = [t["date"].date() for t in txns if t["date"]]
    return (min(days), max(days)) if days else (None, None)
