"""Reconciliation: compare payments read from screenshots with bank statement credits.

Deterministic Python only. No LLM decides whether a payment is genuine.

Statuses
    MATCHED                   UTR found as a bank credit, amount equal, date within tolerance
    AMOUNT_MISMATCH           UTR found as a credit but the amount differs
    UTR_NOT_FOUND             no bank transaction with this UTR, date inside the statement period
    OUTSIDE_STATEMENT_PERIOD  no bank transaction with this UTR, date outside the statement period
    DUPLICATE_CLAIM           another screenshot already claimed this UTR
    NEEDS_REVIEW              anything uncertain (see 'reasons'); never auto-accepted
"""
from collections import defaultdict
from decimal import Decimal

from ..utils.helpers import parse_date, parse_amount, hamming
from .duplicate_service import find_duplicate_claims
from .statement_service import statement_period

MATCHED = "MATCHED"
AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
UTR_NOT_FOUND = "UTR_NOT_FOUND"
OUTSIDE_STATEMENT_PERIOD = "OUTSIDE_STATEMENT_PERIOD"
DUPLICATE_CLAIM = "DUPLICATE_CLAIM"
NEEDS_REVIEW = "NEEDS_REVIEW"


def _result(payment, status, reasons, txn=None, utr_ok=None, amount_ok=None, date_ok=None):
    return {
        "payment_id": payment["id"],
        "status": status,
        "reasons": reasons,
        "checks": {"utr_matched": utr_ok, "amount_matched": amount_ok, "date_matched": date_ok},
        "bank_transaction": ({"row": txn["row"], "utr": txn["utr"], "credit": txn["credit"],
                              "date": txn["date"]} if txn else None),
    }


def match_payment(payment, by_utr, all_utrs, period, date_tolerance_days=1):
    utr = payment.get("utr")
    amount = parse_amount(payment.get("amount"))
    pdate = parse_date(payment.get("date"))
    ocr_flags = list(payment.get("flags") or [])
    reasons = []

    if not utr:
        return _result(payment, NEEDS_REVIEW, ["utr_unreadable"] + ocr_flags)

    candidates = by_utr.get(utr, [])
    if not candidates:
        near = [u for u in all_utrs if hamming(utr, u) == 1]
        if near:  # one digit off a real bank UTR: OCR misread or an edited screenshot
            return _result(payment, NEEDS_REVIEW,
                           [f"utr_differs_by_one_digit_from_bank_utr {near[0]}"] + ocr_flags,
                           utr_ok=False)
        start, end = period
        if pdate and start and end and not (start <= pdate.date() <= end):
            return _result(payment, OUTSIDE_STATEMENT_PERIOD,
                           [f"payment_date {pdate.date()} outside statement {start}..{end}"],
                           utr_ok=False)
        return _result(payment, UTR_NOT_FOUND, ["no_bank_transaction_with_this_utr"], utr_ok=False)

    if len(candidates) > 1:
        return _result(payment, NEEDS_REVIEW, ["multiple_bank_transactions_with_this_utr"],
                       candidates[0], utr_ok=True)
    txn = candidates[0]
    if txn["credit"] <= 0:
        return _result(payment, NEEDS_REVIEW, ["utr_matches_a_debit_not_a_credit"], txn, utr_ok=True)

    amount_ok = amount is not None and amount == txn["credit"]
    if not amount_ok:
        reasons.append(f"amount screenshot={amount} bank={txn['credit']}")

    date_ok = None
    if pdate and txn["date"]:
        date_ok = abs((pdate.date() - txn["date"].date()).days) <= date_tolerance_days
        if not date_ok:
            reasons.append(f"date screenshot={pdate.date()} bank={txn['date'].date()}")
    else:
        reasons.append("date_missing_on_screenshot_or_bank")

    if not amount_ok:
        status = AMOUNT_MISMATCH
    elif date_ok is not True:
        status = NEEDS_REVIEW
    else:
        status = MATCHED
    return _result(payment, status, reasons, txn, utr_ok=True, amount_ok=amount_ok, date_ok=date_ok)


def match_payments(payments, transactions, date_tolerance_days=1):
    """payments: dicts with id, utr, amount, date (+ optional flags/needs_review), in claim order.

    A payment the OCR flagged for review is never auto-accepted: its status is NEEDS_REVIEW
    even when the numbers happen to match, and the bank evidence is still attached.
    """
    by_utr = defaultdict(list)
    for t in transactions:
        if t["utr"]:
            by_utr[t["utr"]].append(t)
    all_utrs = list(by_utr)
    period = statement_period(transactions)
    duplicates = find_duplicate_claims(payments)

    results = []
    for p in payments:
        r = match_payment(p, by_utr, all_utrs, period, date_tolerance_days)
        if p["id"] in duplicates:
            r["reasons"].insert(0, f"same_utr_already_claimed_by {duplicates[p['id']]}")
            r["status"] = DUPLICATE_CLAIM
        elif p.get("needs_review") and r["status"] == MATCHED:
            r["status"] = NEEDS_REVIEW
            r["reasons"].append("ocr_flagged_for_review: " + ", ".join(p.get("flags") or ["unspecified"]))
        results.append(r)
    return results