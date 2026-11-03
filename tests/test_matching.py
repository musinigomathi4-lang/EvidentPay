"""Tests for statement reading, duplicate claims and reconciliation.

    python tests/test_matching.py          Run unit tests
    python tests/test_matching.py --real   Reconcile genuine screenshot data
    python tests/test_matching.py --fake   Reconcile fake screenshot test data
"""
import csv
import sys
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.services.matching_service import (
    match_payments, MATCHED, AMOUNT_MISMATCH, UTR_NOT_FOUND,
    OUTSIDE_STATEMENT_PERIOD, DUPLICATE_CLAIM, NEEDS_REVIEW,
    SENDER_NAME_MISMATCH,
)
from backend.app.services.statement_service import load_statement_csv
from backend.app.services.duplicate_service import find_duplicate_claims


def txn(row, utr, credit, day, debit=0, description=""):
    return {
        "row": row, "utr": utr,
        "credit": Decimal(credit), "debit": Decimal(debit),
        "date": datetime.strptime(day, "%Y-%m-%d"),
        "description": description
    }


def pay(pid, utr, amount, date, **kw):
    return {"id": pid, "utr": utr, "amount": amount, "date": date, **kw}


BANK = [
    txn(1, "614614352249", 90, "2026-05-26"),
    txn(2, "615315443838", 5000, "2026-06-02"),
    txn(3, "088006151542", 600, "2026-08-26"),
    txn(4, "999999999999", 200, "2026-07-01"),
    txn(5, "999999999999", 200, "2026-07-01"),
    txn(6, "111111111111", 0, "2026-07-02", debit=75),
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
    r = status_of(pay("a", "614614352248", 90, "2026-05-26 17:35"))
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
    rs = match_payments([
        pay("24", "615315443838", 5000, "2026-06-02 05:53"),
        pay("25", "615315443838", 5000, "2026-06-02 05:53")
    ], BANK)
    assert [r["status"] for r in rs] == [MATCHED, DUPLICATE_CLAIM]
    assert "24" in rs[1]["reasons"][0]
    assert find_duplicate_claims([
        pay("x", "1", 1, ""), pay("y", None, 1, ""),
        pay("z", "1", 1, "")
    ]) == {"z": "x"}


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


# --- Characterization tests: sender-name check and status precedence (existing behaviour) ---

NAMED_BANK = [txn(1, "543656614964", 1600, "2026-09-15", description="Received from Punna Vanitha")]


def named(payment):
    return match_payments([payment], NAMED_BANK)[0]


def test_sender_name_mismatch_when_both_names_available():
    r = named(pay("a", "543656614964", 1600, "2026-09-15 10:31", sender_name="Suresh Maddali"))
    assert r["status"] == SENDER_NAME_MISMATCH
    assert r["checks"]["sender_matched"] is False
    assert any("sender_name" in x for x in r["reasons"])


def test_sender_name_ignores_case_spacing_and_punctuation():
    r = named(pay("a", "543656614964", 1600, "2026-09-15 10:31", sender_name="PUNNA   vanitha."))
    assert r["status"] == MATCHED and r["checks"]["sender_matched"] is True


def test_sender_not_compared_when_either_name_is_missing():
    r = named(pay("a", "543656614964", 1600, "2026-09-15 10:31"))  # screenshot name missing
    assert r["status"] == MATCHED and "sender_matched" not in r["checks"]
    no_bank_name = [txn(1, "543656614964", 1600, "2026-09-15", description="UPI credit")]
    r = match_payments([pay("a", "543656614964", 1600, "2026-09-15 10:31",
                            sender_name="Suresh Maddali")], no_bank_name)[0]
    assert r["status"] == MATCHED and "sender_matched" not in r["checks"]  # bank name missing


def test_amount_mismatch_takes_precedence_over_sender_mismatch():
    r = named(pay("a", "543656614964", 160, "2026-09-15 10:31", sender_name="Suresh Maddali"))
    assert r["status"] == AMOUNT_MISMATCH


def test_date_review_takes_precedence_over_sender_mismatch():
    r = named(pay("a", "543656614964", 1600, "2026-01-01 10:31", sender_name="Suresh Maddali"))
    assert r["status"] == NEEDS_REVIEW


# --- Unreadable amount: nothing was read, so nothing can mismatch -> NEEDS_REVIEW ---

def test_unreadable_amount_needs_review_not_amount_mismatch():
    r = status_of(pay("a", "614614352249", None, "2026-05-26 17:35"))
    assert r["status"] == NEEDS_REVIEW
    assert r["reasons"][0] == "amount_unreadable"
    assert r["checks"]["amount_matched"] is None          # unknown, not False
    assert not any("amount screenshot=" in x for x in r["reasons"])  # no fake comparison


def test_unreadable_amount_keeps_ocr_flags_and_bank_evidence():
    r = status_of(pay("a", "614614352249", None, "2026-05-26 17:35",
                      needs_review=True, flags=["no_valid_amount_reading"]))
    assert r["status"] == NEEDS_REVIEW
    assert "no_valid_amount_reading" in r["reasons"]
    assert r["checks"]["utr_matched"] is True and r["bank_transaction"]["utr"] == "614614352249"


def test_unparseable_amount_text_is_treated_as_unreadable():
    assert status_of(pay("a", "614614352249", "abc", "2026-05-26 17:35"))["status"] == NEEDS_REVIEW


def test_zero_amount_is_a_real_value_not_unreadable():
    r = status_of(pay("a", "614614352249", 0, "2026-05-26 17:35"))
    assert r["status"] == AMOUNT_MISMATCH and r["checks"]["amount_matched"] is False


def test_unreadable_amount_does_not_change_unmatched_utr_statuses():
    assert status_of(pay("a", "222222222222", None, "2026-06-10 10:00"))["status"] == UTR_NOT_FOUND
    assert status_of(pay("a", "222222222222", None, "2026-12-25 10:00"))["status"] == OUTSIDE_STATEMENT_PERIOD


def test_unreadable_amount_still_reports_duplicate_claim():
    rs = match_payments([pay("24", "615315443838", 5000, "2026-06-02 05:53"),
                         pay("25", "615315443838", None, "2026-06-02 05:53")], BANK)
    assert [r["status"] for r in rs] == [MATCHED, DUPLICATE_CLAIM]


def test_unreadable_amount_still_records_sender_mismatch_in_reasons():
    r = named(pay("a", "543656614964", None, "2026-09-15 10:31", sender_name="Suresh Maddali"))
    assert r["status"] == NEEDS_REVIEW and any("sender_name" in x for x in r["reasons"])


def run_dataset(filename, label, show_all=False):
    from backend.app.utils.helpers import parse_amount

    screenshot_paths = [
        ROOT / "data" / filename,
        ROOT / "backend" / "data" / filename
    ]
    bank_paths = [
        ROOT / "data" / "bank_statement.csv",
        ROOT / "backend" / "data" / "bank_statement.csv"
    ]

    shots = next((p for p in screenshot_paths if p.exists()), None)
    bank = next((p for p in bank_paths if p.exists()), None)

    if not shots or not bank:
        sys.exit(f"Missing {filename} or bank_statement.csv")

    txns = load_statement_csv(bank)

    with open(shots, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        sys.exit(f"No screenshot records found in {shots}")

    headers = list(rows[0].keys())

    def col(*names):
        return next(
            (h for h in headers if any(n in h.lower() for n in names)),
            None
        )

    c_id = col("id", "screenshot")
    c_amt = col("amount")
    c_utr = col("utr")
    c_date = col("date")

    if not all([c_id, c_amt, c_utr, c_date]):
        sys.exit(f"Required columns missing in {shots}")

    payments = [
        pay(
            r[c_id],
            str(r[c_utr]).strip() or None,
            parse_amount(r[c_amt]),
            r[c_date]
        )
        for r in rows
    ]

    print(f"\n{'=' * 15} {label} RECONCILIATION {'=' * 15}")
    print(f"Bank rows: {len(txns)}")
    print(f"Bank credits: {sum(t['credit'] > 0 for t in txns)}")
    print(f"Screenshot claims: {len(payments)}\n")

    results = match_payments(payments, txns)

    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    print("SUMMARY:", counts)
    print("\nINDIVIDUAL RESULTS:")

    for r in results:
        if show_all or r["status"] != MATCHED:
            print(
                f"{r['payment_id']}: {r['status']} "
                f"| Reasons: {r['reasons']}"
            )

    print(f"\nTotal processed: {len(results)}")


def run_real():
    run_dataset("screenshot_data.csv", "REAL")


def run_fake():
    run_dataset("test_screenshot_data.csv", "FAKE", show_all=True)


if __name__ == "__main__":
    if "--real" in sys.argv and "--fake" in sys.argv:
        sys.exit("Choose either --real or --fake.")

    if "--real" in sys.argv:
        run_real()
    elif "--fake" in sys.argv:
        run_fake()
    else:
        fns = [
            v for k, v in sorted(globals().items())
            if k.startswith("test_") and callable(v)
        ]

        for fn in fns:
            fn()
            print("ok  ", fn.__name__)

        print(f"\n{len(fns)} passed")