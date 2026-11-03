
"""End-to-end test: fake screenshots -> OCR -> bank reconciliation."""

import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.services.ocr_service import extract_payment
from backend.app.services.statement_service import load_statement_csv
from backend.app.services.matching_service import match_payments
from backend.app.utils.helpers import parse_amount, parse_date


IMAGE_DIR = ROOT / "uploads" / "screenshots" / "fake_ss"
GROUND_TRUTH = ROOT / "data" / "test_screenshot_data.csv"
BANK_FILE = ROOT / "data" / "bank_statement.csv"


IMAGE_MAP = {
    "TEST001": "outofstatemnt.jpg",
    "TEST002": "outofstatement.jpg",
    "TEST003": "utr.jpg",
    "TEST004": "amtchange.jpg",
    "TEST005": "namechange.jpg",
    "TEST006": "amtchange.jpeg",
    "TEST007": "utrchange.jpeg",
    "TEST008": "datechange.jpeg",
    "TEST009": "amtchange (2).jpeg",
    "TEST010": "datechange (2).jpeg",
}


def expected_date(row):
    date_text = str(row.get("date", "")).strip()
    time_text = str(row.get("time", "")).strip()

    if time_text:
        for fmt in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(f"{date_text} {time_text}", fmt)
            except ValueError:
                pass

    return parse_date(date_text)


def main():
    for path in (IMAGE_DIR, GROUND_TRUTH, BANK_FILE):
        if not path.exists():
            sys.exit(f"Required file or folder not found: {path}")

    with open(GROUND_TRUTH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # Original bank statement is the only source of bank evidence.
    transactions = load_statement_csv(BANK_FILE)

    payments = []
    extraction_results = []

    print("\n========== EVIDENTPAY FAKE IMAGE PIPELINE ==========")
    print("OCR ground truth: test_screenshot_data.csv")
    print("Bank evidence:    bank_statement.csv")

    for row in rows:
        screenshot_id = row["screenshot_id"]

        filename = IMAGE_MAP.get(screenshot_id)
        if not filename:
            sys.exit(f"No image mapping for {screenshot_id}")

        image_path = IMAGE_DIR / filename

        if not image_path.exists():
            sys.exit(f"Image not found: {image_path}")

        print(f"\nProcessing {screenshot_id}: {filename}")

        try:
            extracted = extract_payment(image_path)
        except Exception as exc:
            sys.exit(f"OCR failed for {filename}: {exc}")

        # Ground truth is used ONLY to evaluate OCR accuracy.
        true_amount = parse_amount(row["amount_inr"])
        true_utr = str(row["utr"]).strip() or None
        true_date = expected_date(row)

        actual_amount = parse_amount(extracted["amount"])
        actual_utr = extracted["utr"]
        actual_date = parse_date(extracted["date"])

        amount_ok = true_amount == actual_amount
        utr_ok = true_utr == actual_utr

        date_ok = (
            true_date.date() == actual_date.date()
            if true_date and actual_date
            else true_date is None and actual_date is None
        )

        print("\n  OCR ACCURACY (screenshot ground truth)")
        print(
            f"  Amount: {actual_amount} | "
            f"Screenshot ground truth: {true_amount} | "
            f"{'OK' if amount_ok else 'WRONG'}"
        )
        print(
            f"  UTR: {actual_utr} | "
            f"Screenshot ground truth: {true_utr} | "
            f"{'OK' if utr_ok else 'WRONG'}"
        )
        print(
            f"  Date: {actual_date} | "
            f"Screenshot ground truth: {true_date} | "
            f"{'OK' if date_ok else 'WRONG'}"
        )
        print(f"  OCR flags: {extracted['flags'] or 'None'}")

        extraction_results.append({
            "id": screenshot_id,
            "amount_ok": amount_ok,
            "utr_ok": utr_ok,
            "date_ok": date_ok,
            "flags": extracted["flags"],
        })

        # IMPORTANT:
        # Reconciliation receives OCR output, NOT ground-truth CSV values.
        payments.append({
            "id": screenshot_id,
            "amount": extracted["amount"],
            "utr": extracted["utr"],
            "date": extracted["date"],
            "needs_review": extracted["needs_review"],
            "flags": extracted["flags"],
        })

    print("\n========== BANK RECONCILIATION ==========")
    print("Comparing OCR-extracted claims against original bank statement.")

    results = match_payments(payments, transactions)

    counts = {}

    for result in results:
        status = result["status"]
        counts[status] = counts.get(status, 0) + 1

        print(f"\n{result['payment_id']}: {status}")
        print(f"  Reasons: {result['reasons']}")

        bank_txn = result.get("bank_transaction")

        if bank_txn:
            print("  Bank evidence:")
            print(f"    Transaction row: {bank_txn['row']}")
            print(f"    Bank UTR:        {bank_txn['utr']}")
            print(f"    Bank amount:     {bank_txn['credit']}")
            print(f"    Bank date:       {bank_txn['date']}")
        else:
            print("  Bank evidence: No matching transaction identified.")

    print("\n========== OCR ACCURACY SUMMARY ==========")

    total = len(extraction_results)

    for field in ("amount_ok", "utr_ok", "date_ok"):
        correct = sum(r[field] for r in extraction_results)
        print(f"{field}: {correct}/{total}")

    fully_correct = sum(
        all(r[field] for field in ("amount_ok", "utr_ok", "date_ok"))
        for r in extraction_results
    )

    flagged = sum(bool(r["flags"]) for r in extraction_results)

    print(f"\nAll fields correct: {fully_correct}/{total}")
    print(f"Flagged for review: {flagged}/{total}")

    print("\n========== RECONCILIATION SUMMARY ==========")
    print(f"Total screenshots: {len(results)}")

    for status, count in counts.items():
        print(f"{status}: {count}")

    print("\nPipeline test completed.")


if __name__ == "__main__":
    main()
