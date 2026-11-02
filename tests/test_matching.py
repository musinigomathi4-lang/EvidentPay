"""Tests for statement reading, duplicate claims and reconciliation.

    pytest tests/test_matching.py          (or: python tests/test_matching.py)
    python tests/test_matching.py --real   reconcile data/screenshot_data.csv against
                                           data/bank_statement.csv and print the outcome
"""
import csv
import sys
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.services.matching_service import (  # noqa: E402
    match_payments, MATCHED, AMOUNT_MISMATCH, UTR_NOT_FOUND, OUTSIDE_STATEMENT_PERIOD,
    DUPLICATE_CLAIM, NEEDS_REVIEW,
)
from backend.app.services.statement_service import load_statement_csv  # noqa: E402
from backend.app.services.duplicate_service import find_duplicate_claims  # noqa: E402


def txn(row, utr, credit, day, debit=0):
    return {"row": row, "utr": utr, "credit": Decimal(credit), "debit": Decimal(debit),
            "date": datetime.strptime(day, "%Y-%m-%d"), "description": ""}


def pay(pid, utr, amount, date, **kw):
    return {"id": pid, "utr": utr, "amount": amount, "date": date, **kw}


BANK = [
    txn(1, "614614352249", 90, "2026-05-26"),
    txn(2, "615315443838", 5000, "2026-06-02"),
    txn(3, "088006151542", 600, "2026-08-26"),
    txn(4, "999999999999", 200, "2026-07-01", debit=0),
    txn(5, "999999999999", 200, "2026-07-01"),                  # same UTR twice in the bank
    txn(6, "111111111111", 0, "2026-07-02", debit=75),          # a debit
]


def status_of(payment, bank=BANK):
    return match_payments([payment], bank)[0]


def test_correct_payment_matches():
    r = status_of(pay("a", "614614352249", 90, "2026-05-26 17:35"))
    assert r["status"] == MATCHED and r["checks"] == {
        "utr_matched": True, "amount_matched": True, "date_matched": True}


def test_leading_zero_utr_matches_as_text():
    assert status_of(pay("a", "088006151542", 600, "2026-08-26 21:04"))["status"] == MATCHED


def test_amount_mismatch():
    r = status_of(pay("a", "614614352249", 900, "2026-05-26 17:35"))
    assert r["status"] == AMOUNT_MISMATCH and r["checks"]["amount_matched"] is False


def test_utr_not_found_inside_statement_period():
    assert status_of(pay("a", "222222222222", 90, "2026-06-10 10:00"))["status"] == UTR_NOT_FOUND


def test_payment_outside_statement_period():
    assert status_of(pay("a", "222222222222", 90, "2026-12-25 10:00"))["status"] == OUTSIDE_STATEMENT_PERIOD


def test_one_digit_off_utr_needs_review():
    r = status_of(pay("a", "614614352248", 90, "2026-05-26 17:35"))   # last digit changed
    assert r["status"] == NEEDS_REVIEW and "one_digit" in r["reasons"][0]


def test_date_one_day_apart_is_tolerated_but_far_is_review():
    assert status_of(pay("a", "614614352249", 90, "2026-05-27 00:10"))["status"] == MATCHED
    assert status_of(pay("a", "614614352249", 90, "2026-05-01 10:00"))["status"] == NEEDS_REVIEW


def test_multiple_bank_transactions_with_same_utr_needs_review():
    assert status_of(pay("a", "999999999999", 200, "2026-07-01 10:00"))["status"] == NEEDS_REVIEW


def test_utr_matching_a_debit_needs_review():
    assert status_of(pay("a", "111111111111", 75, "2026-07-02 10:00"))["status"] == NEEDS_REVIEW


def test_unreadable_utr_needs_review():
    assert status_of(pay("a", None, 90, "2026-05-26", flags=["utr_not_found"]))["status"] == NEEDS_REVIEW


def test_ocr_flagged_payment_is_never_auto_matched():
    r = status_of(pay("a", "614614352249", 90, "2026-05-26 17:35",
                      needs_review=True, flags=["amount_scale_disagreement"]))
    assert r["status"] == NEEDS_REVIEW and r["checks"]["utr_matched"] is True


def test_duplicate_claim_first_wins():
    rs = match_payments([pay("24", "615315443838", 5000, "2026-06-02 05:53"),
                         pay("25", "615315443838", 5000, "2026-06-02 05:53")], BANK)
    assert [r["status"] for r in rs] == [MATCHED, DUPLICATE_CLAIM]
    assert "24" in rs[1]["reasons"][0]
    assert find_duplicate_claims([pay("x", "1", 1, ""), pay("y", None, 1, ""), pay("z", "1", 1, "")]) == {"z": "x"}


def test_statement_csv_with_utr_inside_narration():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "bank.csv"
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Txn Date", "Narration", "Withdrawal Amt.", "Deposit Amt.", "Balance"])
            w.writerow(["26-05-2026", "UPI/614614352249/Mamatha Reddy/SBI", "", "90.00", "1,000.00"])
            w.writerow(["27-05-2026", "UPI/123456789012/Shop", "200.00", "", "800.00"])
        t = load_statement_csv(p)
    assert t[0]["utr"] == "614614352249" and t[0]["credit"] == Decimal("90.00")
    assert t[0]["date"] == datetime(2026, 5, 26)
    assert t[1]["debit"] == Decimal("200.00") and t[1]["credit"] == 0


def run_real():
    from backend.app.utils.helpers import parse_amount
    shots = next((p for p in (ROOT / "data" / "screenshot_data.csv", ROOT / "backend" / "data" / "screenshot_data.csv") if p.exists()), None)
    bank = next((p for p in (ROOT / "data" / "bank_statement.csv", ROOT / "backend" / "data" / "bank_statement.csv") if p.exists()), None)
    if not shots or not bank:
        sys.exit("need data/screenshot_data.csv and data/bank_statement.csv")
    txns = load_statement_csv(bank)
    rows = list(csv.DictReader(open(shots, newline="", encoding="utf-8-sig")))
    h = list(rows[0].keys())
    col = lambda *n: next((x for x in h if any(k in x.lower() for k in n)), None)
    c_id, c_amt, c_utr, c_date = col("id", "screenshot"), col("amount"), col("utr"), col("date")
    payments = [pay(r[c_id], str(r[c_utr]).strip() or None, parse_amount(r[c_amt]), r[c_date]) for r in rows]
    print(f"{len(txns)} bank rows ({sum(t['credit'] > 0 for t in txns)} credits), "
          f"{sum(t['utr'] is not None for t in txns)} with a readable UTR; {len(payments)} screenshot rows\n")
    results = match_payments(payments, txns)
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(counts, "\n")
    for r in results:
        if r["status"] != MATCHED:
            print(f"  {r['payment_id']}: {r['status']} {r['reasons']}")


if __name__ == "__main__":
    if "--real" in sys.argv:
        run_real()
    else:
        fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
        for fn in fns:
            fn()
            print("ok  ", fn.__name__)
        print(f"\n{len(fns)} passed")