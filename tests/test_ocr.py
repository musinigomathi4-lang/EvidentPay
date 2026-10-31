"""OCR accuracy test.

Run the report (from the EvidentPay2 folder):
    python tests/test_ocr.py [ground_truth.csv] [screenshots_dir]
Run as a test:
    pytest tests/test_ocr.py

Ground-truth CSV needs a file-name column and an 'amount' column; 'utr' and 'date' columns
are scored too when present. Header names are matched loosely ('screenshot'/'file'/'image',
anything containing 'amount', 'utr', 'date'). Amounts may include the rupee sign and commas.

The number that matters most for an evidence tool is SILENT errors: wrong values that were
NOT flagged for manual review. The pytest check fails if there are any.
"""
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the folder that contains backend/ and tests/
sys.path.insert(0, str(ROOT))

from backend.app.services.ocr_service import extract_payment  # noqa: E402
from backend.app.utils.validators import parse_gpay_date  # noqa: E402

IMG_EXT = (".jpeg", ".jpg", ".png")


def _first_existing(candidates):
    for c in candidates:
        if Path(c).exists():
            return Path(c)
    return Path(candidates[0])


DEFAULT_CSV = _first_existing([
    ROOT / "data" / "test_screenshot_data.csv",
    ROOT / "backend" / "data" / "test_screenshot_data.csv",
])
DEFAULT_DIR = _first_existing([
    os.environ.get("OCR_SCREENSHOT_DIR") or ROOT / "uploads" / "screenshots",
    ROOT / "uploads" / "screenshots",
    ROOT / "backend" / "uploads" / "screenshots",
])


def _col(header, *needles, exclude=()):
    for h in header:
        low = h.lower()
        if any(n in low for n in needles) and not any(x in low for x in exclude):
            return h
    return None


def _norm_amount(s):
    s = "".join(ch for ch in str(s) if ch.isdigit())
    return int(s) if s else None


def _norm_date(s):
    d = parse_gpay_date(str(s))
    if d:
        return d.strftime("%Y-%m-%d %H:%M")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(str(s).strip(), fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
    return None


def _find_image(folder: Path, name: str):
    stem = Path(name).stem
    for ext in IMG_EXT:
        p = folder / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def run(csv_path=DEFAULT_CSV, img_dir=DEFAULT_DIR):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    header = list(rows[0].keys())
    c_file = _col(header, "screenshot", "file", "image", "name")
    c_amt = _col(header, "amount")
    c_utr = _col(header, "utr", "transaction", exclude=("google",))
    c_date = _col(header, "date")
    assert c_file and c_amt, f"CSV needs a file column and an amount column, got {header}"

    stats = {k: {"ok": 0, "n": 0, "silent": 0} for k in ("amount", "utr", "date")}
    report = []
    for r in rows:
        img = _find_image(Path(img_dir), r[c_file])
        if img is None:
            report.append((r[c_file], "MISSING IMAGE"))
            continue
        out = extract_payment(img)
        checks = {"amount": (_norm_amount(r[c_amt]), out["amount"])}
        if c_utr:
            checks["utr"] = (str(r[c_utr]).strip(), out["utr"])
        if c_date:
            truth = _norm_date(r[c_date])
            if truth:
                checks["date"] = (truth, out["date"])
        for field, (truth, got) in checks.items():
            stats[field]["n"] += 1
            if truth == got:
                stats[field]["ok"] += 1
            else:
                flagged = out["needs_review"]
                stats[field]["silent"] += 0 if flagged else 1
                report.append((r[c_file], f"{field}: expected {truth!r}, got {got!r}, "
                                          f"{'flagged' if flagged else 'SILENT'} {out['flags']}"))
    return stats, report


def print_report(stats, report):
    print(f"{'field':8} {'correct':>10} {'silent errors':>14}")
    for k, s in stats.items():
        if s["n"]:
            print(f"{k:8} {s['ok']:>4}/{s['n']:<5} {s['silent']:>14}")
    for name, msg in report:
        print(f"  {name}: {msg}")


def test_no_silent_errors():
    import pytest
    if not Path(DEFAULT_CSV).exists() or not Path(DEFAULT_DIR).exists():
        pytest.skip("ground-truth CSV or screenshots folder not found")
    stats, report = run()
    print_report(stats, report)
    assert all(s["silent"] == 0 for s in stats.values()), "wrong values that were not flagged for review"


if __name__ == "__main__":
    csv_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    dir_arg = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DIR
    print_report(*run(csv_arg, dir_arg))