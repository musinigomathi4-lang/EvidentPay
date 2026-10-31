"""Score amount_ocr.read_amount against your true amounts.

Usage:  python eval_amounts.py <screenshots_folder> <truth.csv>

truth.csv has a header and two columns, plain numbers without commas or the rupee sign:
    screenshot,amount
    1.jpeg,14000
    16.jpeg,50
"""
import csv
import os
import sys

from amount_ocr import read_amount


def main(folder, truth_csv):
    with open(truth_csv, newline="") as f:
        truth = {r["screenshot"].strip(): int(r["amount"].replace(",", "")) for r in csv.DictReader(f)}

    correct = flagged = wrong_unflagged = missing = 0
    rows = []
    for name, true_amt in truth.items():
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            missing += 1
            rows.append((name, true_amt, None, "FILE NOT FOUND"))
            continue
        res = read_amount(path)
        got, ok = res.get("amount"), res.get("ok")
        if got == true_amt:
            correct += 1
            status = "ok" if ok else "ok (but flagged for review)"
            flagged += 0 if ok else 1
        elif not ok:
            flagged += 1
            status = "WRONG, flagged for review"
        else:
            wrong_unflagged += 1
            status = "WRONG and NOT flagged  <-- the dangerous kind"
        rows.append((name, true_amt, got, status))

    for r in rows:
        if not r[3].startswith("ok"):
            print(f"{r[0]:<12} true={r[1]:<8} got={r[2]!s:<8} {r[3]}")
    total = len(truth) - missing
    print(f"\n{correct}/{total} correct | {flagged} flagged for review | "
          f"{wrong_unflagged} wrong and unflagged | {missing} files missing")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
