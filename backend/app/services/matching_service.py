
"""Reconciliation: compare screenshot payments with bank statement credits.

Deterministic Python only. No LLM decides whether a payment is genuine.
"""
from collections import defaultdict
from decimal import Decimal
import re

from ..utils.helpers import parse_date, parse_amount, hamming
from .duplicate_service import find_duplicate_claims
from .statement_service import statement_period

MATCHED = "MATCHED"
AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
UTR_NOT_FOUND = "UTR_NOT_FOUND"
OUTSIDE_STATEMENT_PERIOD = "OUTSIDE_STATEMENT_PERIOD"
DUPLICATE_CLAIM = "DUPLICATE_CLAIM"
NEEDS_REVIEW = "NEEDS_REVIEW"
SENDER_NAME_MISMATCH = "SENDER_NAME_MISMATCH"


def _result(payment, status, reasons, txn=None, utr_ok=None,
            amount_ok=None, date_ok=None, sender_ok=None):
    checks = {
        "utr_matched": utr_ok,
        "amount_matched": amount_ok,
        "date_matched": date_ok,
    }

    if sender_ok is not None:
        checks["sender_matched"] = sender_ok

    return {
        "payment_id": payment["id"],
        "status": status,
        "reasons": reasons,
        "checks": checks,
        "bank_transaction": (
            {
                "row": txn["row"],
                "utr": txn["utr"],
                "credit": txn["credit"],
                "date": txn["date"],
            } if txn else None
        ),
    }


def _extract_sender_name(description):
    """Extract sender from descriptions such as 'Received from NAME'."""
    match = re.match(
        r"^\s*received\s+from\s+(.+?)\s*$",
        str(description or ""),
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _normalize_name(name):
    """Ignore capitalization, spaces and punctuation when comparing names."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def match_payment(payment, by_utr, all_utrs, period,
                  date_tolerance_days=1):
    utr = payment.get("utr")
    amount = parse_amount(payment.get("amount"))
    pdate = parse_date(payment.get("date"))
    ocr_flags = list(payment.get("flags") or [])
    reasons = []

    if not utr:
        return _result(
            payment, NEEDS_REVIEW,
            ["utr_unreadable"] + ocr_flags
        )

    candidates = by_utr.get(utr, [])

    if not candidates:
        near = [u for u in all_utrs if hamming(utr, u) == 1]

        if near:
            return _result(
                payment, NEEDS_REVIEW,
                [f"utr_differs_by_one_digit_from_bank_utr {near[0]}"]
                + ocr_flags,
                utr_ok=False,
            )

        start, end = period

        if pdate and start and end and not (
            start <= pdate.date() <= end
        ):
            return _result(
                payment, OUTSIDE_STATEMENT_PERIOD,
                [f"payment_date {pdate.date()} outside statement {start}..{end}"],
                utr_ok=False,
            )

        return _result(
            payment, UTR_NOT_FOUND,
            ["no_bank_transaction_with_this_utr"],
            utr_ok=False,
        )

    if len(candidates) > 1:
        return _result(
            payment, NEEDS_REVIEW,
            ["multiple_bank_transactions_with_this_utr"],
            candidates[0], utr_ok=True,
        )

    txn = candidates[0]

    if txn["credit"] <= 0:
        return _result(
            payment, NEEDS_REVIEW,
            ["utr_matches_a_debit_not_a_credit"],
            txn, utr_ok=True,
        )

    # Amount comparison
    amount_ok = amount is not None and amount == txn["credit"]

    if not amount_ok:
        reasons.append(
            f"amount screenshot={amount} bank={txn['credit']}"
        )

    # Date comparison
    date_ok = None

    if pdate and txn["date"]:
        date_ok = (
            abs((pdate.date() - txn["date"].date()).days)
            <= date_tolerance_days
        )

        if not date_ok:
            reasons.append(
                f"date screenshot={pdate.date()} bank={txn['date'].date()}"
            )
    else:
        reasons.append("date_missing_on_screenshot_or_bank")

    # Sender-name comparison (only when both names are available)
    sender_ok = None
    screenshot_sender = payment.get("sender_name")
    bank_sender = _extract_sender_name(txn.get("description"))

    if screenshot_sender and bank_sender:
        sender_ok = (
            _normalize_name(screenshot_sender)
            == _normalize_name(bank_sender)
        )

        if not sender_ok:
            reasons.append(
                f"sender_name screenshot={screenshot_sender} "
                f"bank={bank_sender}"
            )

    # Determine final status
    if not amount_ok:
        status = AMOUNT_MISMATCH
    elif date_ok is not True:
        status = NEEDS_REVIEW
    elif sender_ok is False:
        status = SENDER_NAME_MISMATCH
    else:
        status = MATCHED

    return _result(
        payment, status, reasons, txn,
        utr_ok=True,
        amount_ok=amount_ok,
        date_ok=date_ok,
        sender_ok=sender_ok,
    )


def match_payments(payments, transactions, date_tolerance_days=1):
    """Reconcile screenshot claims against bank transactions."""

    by_utr = defaultdict(list)

    for transaction in transactions:
        if transaction["utr"]:
            by_utr[transaction["utr"]].append(transaction)

    all_utrs = list(by_utr)
    period = statement_period(transactions)
    duplicates = find_duplicate_claims(payments)

    results = []

    for payment in payments:
        result = match_payment(
            payment, by_utr, all_utrs, period, date_tolerance_days
        )

        if payment["id"] in duplicates:
            result["reasons"].insert(
                0, f"same_utr_already_claimed_by {duplicates[payment['id']]}"
            )
            result["status"] = DUPLICATE_CLAIM

        elif payment.get("needs_review") and result["status"] == MATCHED:
            result["status"] = NEEDS_REVIEW
            result["reasons"].append(
                "ocr_flagged_for_review: "
                + ", ".join(payment.get("flags") or ["unspecified"])
            )

        results.append(result)

    return results
