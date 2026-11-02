"""Bank statement reading (CSV for now; PDF support can be added behind the same output shape).

Output: a list of transactions, each
    {"row": int, "date": datetime|None, "utr": str|None, "credit": Decimal, "debit": Decimal,
     "description": str}
The UTR is taken from a reference/UTR column when present, otherwise found inside the narration
(bank narrations usually look like 'UPI/614614352249/...').
"""
import csv
from decimal import Decimal

from ..utils.helpers import parse_date, parse_amount, extract_utr


def _find(header, *needles, exclude=()):
    for h in header:
        low = h.lower().replace("_", " ")
        if any(n in low for n in needles) and not any(x in low for x in exclude):
            return h
    return None


def load_statement_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    header = list(rows[0].keys())
    c_date = (_find(header, "txn date", "transaction date", "value date", "posting date")
              or _find(header, "date"))
    c_utr = _find(header, "utr", "reference", "ref no", "ref.", "ref")
    c_desc = _find(header, "description", "narration", "particulars", "remarks", "details")
    c_credit = _find(header, "credit", "deposit", "cr amount", "received")
    c_debit = _find(header, "debit", "withdrawal", "dr amount", "paid")
    c_amount = _find(header, "amount", exclude=("credit", "debit"))
    c_type = _find(header, "type", "dr/cr", "cr/dr")

    txns = []
    for i, r in enumerate(rows, start=1):
        desc = str(r.get(c_desc, "") or "") if c_desc else ""
        credit = parse_amount(r.get(c_credit)) if c_credit else None
        debit = parse_amount(r.get(c_debit)) if c_debit else None
        if credit is None and debit is None and c_amount:  # single amount column + type
            amt = parse_amount(r.get(c_amount))
            kind = str(r.get(c_type, "") if c_type else "").strip().lower()
            if amt is not None:
                if kind.startswith(("cr", "credit")):
                    credit = amt
                elif kind.startswith(("dr", "debit")):
                    debit = amt
        txns.append({
            "row": i,
            "date": parse_date(r.get(c_date)) if c_date else None,
            "utr": extract_utr(r.get(c_utr) if c_utr else None, desc),
            "credit": credit or Decimal(0),
            "debit": debit or Decimal(0),
            "description": desc,
        })
    return txns


def statement_period(txns):
    """(first_day, last_day) covered by the statement, as dates, or (None, None)."""
    days = [t["date"].date() for t in txns if t["date"]]
    return (min(days), max(days)) if days else (None, None)