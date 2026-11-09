"""OCR accuracy test against the real screenshots (uploads/screenshots/real_ss).

Run the report (from the EvidentPay folder):
    python tests/test_ocr.py [ground_truth.csv] [screenshots_dir]
Run as a test:
    pytest tests/test_ocr.py

Ground truth = data/screenshot_data.csv (Screenshot ID, Amount, UTR, Date). Rows are linked to
images by file name ('16.jpeg', '16') or by the number inside the ID ('SS016' -> 16.jpeg). If
neither works and the row count equals the image count, rows are linked by order (a warning
is printed). data/test_screenshot_data.csv holds the deliberately modified records and is
never used here.

Unlabelled screenshots (light mode, other phones, WhatsApp copies, failed payments, other apps)?
    python tests/test_ocr.py --survey path\\to\\folder
runs the OCR on every image in the folder and prints one line each (amount, UTR, date, status,
flags). Lines marked CHECK BY EYE were not flagged for review: compare those to the image.

No ground-truth file at all?   python tests/test_ocr.py --template
writes data/ocr_ground_truth.csv listing every image with empty amount/utr/date columns.

Dates in the CSV may be '24-07-2026' (date only: compared on the day) or include a time.
The number that matters most for an evidence tool is SILENT errors: wrong values that were
NOT flagged for manual review. The pytest check fails if there are any.
"""
import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the folder that contains backend/ and tests/
sys.path.insert(0, str(ROOT))

from backend.app.services.ocr_service import extract_payment  # noqa: E402
from backend.app.utils.validators import parse_gpay_date  # noqa: E402

IMG_EXT = (".jpeg", ".jpg", ".png")

# real_ss only: fake_ss holds tampered copies that must never count towards accuracy
IMG_DIR_CANDIDATES = [
    os.environ.get("OCR_SCREENSHOT_DIR"),
    ROOT / "uploads" / "screenshots" / "real_ss",
    ROOT / "backend" / "uploads" / "screenshots" / "real_ss",
]
# test_screenshot_data.csv (modified/fake records) is deliberately NOT listed
CSV_CANDIDATES = [
    ROOT / "data" / "ocr_ground_truth.csv",
    ROOT / "backend" / "data" / "ocr_ground_truth.csv",
    ROOT / "data" / "screenshot_data.csv",
    ROOT / "backend" / "data" / "screenshot_data.csv",
]
ID_WORDS = ("screenshot", "file", "image", "name", "id")
NOT_ID_WORDS = ("utr", "transaction", "amount", "date", "google")


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
    """-> (YYYY-MM-DD, 'HH:MM' or None) or None if unparseable."""
    s = str(s).strip()
    if not s:
        return None
    has_explicit_time = bool(re.search(r"\\d{1,2}:\\d{2}", s))
    d = parse_gpay_date(s)
    if d:
        return d.strftime("%Y-%m-%d"), (d.strftime("%H:%M") if has_explicit_time else None)
    for fmt, has_time in (("%Y-%m-%d %H:%M", 1), ("%Y-%m-%d %H:%M:%S", 1), ("%d-%m-%Y %H:%M", 1),
                          ("%d/%m/%Y %H:%M", 1), ("%Y-%m-%d", 0), ("%d-%m-%Y", 0),
                          ("%d/%m/%Y", 0), ("%d %b %Y", 0), ("%d %B %Y", 0), ("%d %b, %Y", 0)):
        try:
            d = datetime.strptime(s, fmt)
            return d.strftime("%Y-%m-%d"), (d.strftime("%H:%M") if has_time else None)
        except ValueError:
            pass
    return None


def _find_image(folder: Path, name: str):
    stem = Path(str(name).strip()).stem
    for ext in IMG_EXT:
        p = folder / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def _images(img_dir):
    imgs = [p for p in Path(img_dir).iterdir() if p.suffix.lower() in IMG_EXT]
    return sorted(imgs, key=lambda p: (int(p.stem) if p.stem.isdigit() else 10**9, p.name))


def _read_rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _map_rows(rows, img_dir):
    """Link CSV rows to image files. Returns (pairs [(row, path)], how_it_was_linked)."""
    img_dir = Path(img_dir)
    header = list(rows[0].keys())
    id_cols = [h for h in header
               if any(w in h.lower() for w in ID_WORDS) and not any(w in h.lower() for w in NOT_ID_WORDS)]
    best, how = [], ""
    for h in id_cols:
        direct = [(r, _find_image(img_dir, r[h])) for r in rows if r.get(h)]
        direct = [(r, p) for r, p in direct if p]
        if len(direct) > len(best):
            best, how = direct, f"file name in column '{h}'"
        by_num = []
        for r in rows:
            m = re.search(r"\d+", str(r.get(h, "")))
            p = _find_image(img_dir, str(int(m.group()))) if m else None
            if p:
                by_num.append((r, p))
        if len(by_num) > len(best):
            best, how = by_num, f"number inside '{h}' (e.g. {rows[0][h]} -> {by_num[0][1].name})"
    if not best:
        imgs = _images(img_dir)
        if len(imgs) == len(rows):
            best = list(zip(rows, imgs))
            how = "ROW ORDER (IDs did not match any file; if many rows mismatch, the order assumption is wrong)"
    return best, how


def pick_img_dir():
    for c in IMG_DIR_CANDIDATES:
        if c and Path(c).is_dir():
            return Path(c)
    return None


def pick_csv(img_dir):
    best, best_n = None, 0
    for c in CSV_CANDIDATES:
        if c.exists():
            rows = _read_rows(c)
            if rows:
                n = len(_map_rows(rows, img_dir)[0])
                if n > best_n:
                    best, best_n = c, n
    return best


def write_template(img_dir):
    out = ROOT / "data" / "ocr_ground_truth.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["screenshot", "amount", "utr", "date"])
        for p in _images(img_dir):
            w.writerow([p.name, "", "", ""])
    print(f"Wrote {out}. Fill in the amount column, then run the report.")


def _diagnostics():
    lines = []
    for c in CSV_CANDIDATES:
        if c.exists():
            rows = _read_rows(c)
            lines.append(f"  {c}\n    columns: {list(rows[0].keys()) if rows else 'EMPTY FILE'}"
                         f"\n    first row: {rows[0] if rows else '-'}")
    return "\n".join(lines) or "  (no ground-truth CSV found in data/)"


def run(csv_path, img_dir):
    rows = _read_rows(csv_path)
    header = list(rows[0].keys())
    c_amt = _col(header, "amount")
    c_utr = _col(header, "utr", "transaction", exclude=("google",))
    c_date = _col(header, "date")
    assert c_amt, f"CSV needs an amount column, got {header}"
    pairs, how = _map_rows(rows, img_dir)

    stats = {k: {"ok": 0, "n": 0, "silent": 0} for k in ("amount", "utr", "date")}
    report = []
    for r, img in pairs:
        out = extract_payment(img)
        checks = {}
        if _norm_amount(r[c_amt]) is not None:
            checks["amount"] = (_norm_amount(r[c_amt]), out["amount"])
        if c_utr and str(r[c_utr]).strip():
            checks["utr"] = (str(r[c_utr]).strip(), out["utr"])
        if c_date and _norm_date(r[c_date]):
            day, tm = _norm_date(r[c_date])
            got = out["date"] or ""
            got = got if tm else got[:10]            # date-only truth: compare the day
            checks["date"] = (f"{day} {tm}" if tm else day, got or None)
        for field, (truth, got) in checks.items():
            stats[field]["n"] += 1
            if truth == got:
                stats[field]["ok"] += 1
            else:
                flagged = out["needs_review"]
                stats[field]["silent"] += 0 if flagged else 1
                report.append((img.name, f"{field}: expected {truth!r}, got {got!r}, "
                                         f"{'flagged' if flagged else 'SILENT'} {out['flags']}"))
    return stats, report, how, len(pairs), len(rows)


def print_report(stats, report, how="", linked=0, total=0):
    if how:
        print(f"Linked {linked}/{total} rows to images by {how}\n")
    print(f"{'field':8} {'correct':>10} {'silent errors':>14}")
    for k, s in stats.items():
        if s["n"]:
            print(f"{k:8} {s['ok']:>4}/{s['n']:<5} {s['silent']:>14}")
    for name, msg in report:
        print(f"  {name}: {msg}")


def survey(folder):
    folder = Path(folder)
    if not folder.is_dir():
        sys.exit(f"Folder not found: {folder}")
    imgs = _images(folder)
    flagged = 0
    for p in imgs:
        o = extract_payment(p)
        flagged += o["needs_review"]
        mark = "flagged" if o["needs_review"] else "CHECK BY EYE"
        print(f"{p.name:28} amount={o['amount']!s:>8} utr={o['utr']!s:>12} date={o['date']!s:>16} "
              f"status={o['status']!s:>10}  [{mark}] {[f[:50] for f in o['flags']]}")
    print(f"\n{len(imgs)} images: {flagged} flagged for review, {len(imgs) - flagged} to check by eye")


def _resolve(csv_arg=None, dir_arg=None):
    img_dir = Path(dir_arg) if dir_arg else pick_img_dir()
    if img_dir is None or not img_dir.is_dir():
        sys.exit(f"Screenshots folder not found. Looked for: {[str(c) for c in IMG_DIR_CANDIDATES if c]}")
    csv_path = Path(csv_arg) if csv_arg else pick_csv(img_dir)
    if csv_path is None:
        sys.exit(f"Could not link any CSV rows to the images in {img_dir}\n"
                 f"CSV files I checked:\n{_diagnostics()}\n\n"
                 "To create a ready-to-fill file listing every image, run:\n"
                 "    python tests/test_ocr.py --template")
    print(f"CSV:    {csv_path}\nImages: {img_dir}")
    return csv_path, img_dir


def test_no_silent_errors():
    import pytest
    img_dir = pick_img_dir()
    csv_path = pick_csv(img_dir) if img_dir else None
    if csv_path is None:
        pytest.skip("no ground-truth CSV linking to the screenshots folder")
    stats, report, how, linked, total = run(csv_path, img_dir)
    print_report(stats, report, how, linked, total)
    assert all(s["silent"] == 0 for s in stats.values()), "wrong values that were not flagged for review"


if __name__ == "__main__":
    if "--survey" in sys.argv:
        i = sys.argv.index("--survey")
        sys.exit(survey(sys.argv[i + 1]) if len(sys.argv) > i + 1 else "usage: --survey <folder>")
    if "--template" in sys.argv:
        d = pick_img_dir()
        sys.exit("Screenshots folder not found" if d is None else write_template(d))
    csv_path, img_dir = _resolve(sys.argv[1] if len(sys.argv) > 1 else None,
                                 sys.argv[2] if len(sys.argv) > 2 else None)
    print_report(*run(csv_path, img_dir))