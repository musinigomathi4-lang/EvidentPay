"""Amount extraction for Google Pay screenshots (EvidentPay).

Idea: the rupee glyph is OCR'd unreliably (read as 2, %, *, or dropped), so we
never ask Tesseract to read it. We find the amount row, split it into connected
components, identify the rupee glyph by shape, cut it off, and OCR only digits.
"""
import re
import cv2
import numpy as np
import pytesseract
from pytesseract import Output

# Indian grouping: 0-999, or 1-2 digits then (,dd)* then ,ddd  (e.g. 5,000 / 12,500 / 1,25,000)
AMOUNT_RE = re.compile(r"^(\d{1,3}|\d{1,2}(,\d{2})*,\d{3})$")


def find_amount_box(img):
    """Amount is the largest text on the screen: take the tallest digit-bearing words."""
    d = pytesseract.image_to_data(img, config="--psm 4", output_type=Output.DICT)
    words = [i for i, t in enumerate(d["text"]) if re.search(r"\d", t) and d["height"][i] > 0]
    if not words:
        return None
    tallest = max(d["height"][i] for i in words)
    row = [i for i in words if d["height"][i] >= 0.7 * tallest]
    x0 = min(d["left"][i] for i in row)
    x1 = max(d["left"][i] + d["width"][i] for i in row)
    y0 = min(d["top"][i] for i in row)
    y1 = max(d["top"][i] + d["height"][i] for i in row)
    return x0, y0, x1, y1


def binarize(gray):
    _, b = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    if (b > 0).mean() > 0.5:  # text must be the minority colour
        b = 255 - b
    return b  # text = 255


def looks_like_rupee(comp):
    """Rupee has two horizontal bars across its upper half; digits 2/5/7 have at most one."""
    h, w = comp.shape
    top = comp[: int(h * 0.55)]
    full_rows = (top > 0).mean(axis=1) > 0.6
    runs = np.diff(np.concatenate([[0], full_rows.astype(int), [0]]))
    return int((runs == 1).sum()) >= 2


def read_amount(path):
    img = cv2.imread(path)
    box = find_amount_box(img)
    if box is None:
        return {"amount": None, "ok": False, "flags": ["no_amount_line"]}
    x0, y0, x1, y1 = box
    pad = 12
    # extend left so the rupee glyph is inside the crop even if OCR dropped it
    crop = img[max(y0 - pad, 0): y1 + pad, max(x0 - 90, 0): x1 + pad]
    bw = binarize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))

    n, _, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    comps = [stats[i] for i in range(1, n) if stats[i][4] > 40 and stats[i][3] > 0.25 * bw.shape[0]]
    comps.sort(key=lambda s: s[0])
    flags = []
    if len(comps) < 2:
        return {"amount": None, "ok": False, "flags": ["too_few_glyphs"]}

    x, y, w, h, _ = comps[0]
    if not looks_like_rupee(bw[y:y + h, x:x + w]):
        flags.append("leftmost_glyph_not_rupee")  # do not silently strip a real digit
        cut = 0
    else:
        cut = x + w + 1

    digits = 255 - bw[:, cut:]  # black text on white for Tesseract
    # Tesseract is scale-sensitive on big glyphs (a 5 can read as 9), so read at
    # several digit heights and vote. Disagreement => manual review.
    votes = {}
    for target_h in (28, 32, 36, 40, 44, 48, 52):
        r = target_h / digits.shape[0]
        im = cv2.resize(digits, None, fx=r, fy=r, interpolation=cv2.INTER_AREA)
        im = cv2.copyMakeBorder(im, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
        t = pytesseract.image_to_string(
            im, config="--psm 7 -c tessedit_char_whitelist=0123456789,"
        ).strip()
        if AMOUNT_RE.match(t):
            votes[t] = votes.get(t, 0) + 1
    if not votes:
        return {"amount": None, "ok": False, "flags": flags + ["no_valid_reading"]}
    txt = max(votes, key=votes.get)
    if votes[txt] < 7:
        flags.append(f"scale_disagreement {votes}")
    ok = not flags
    value = int(txt.replace(",", ""))
    return {"amount_text": txt, "amount": value, "ok": ok, "flags": flags, "votes": votes}


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        print(p, read_amount(p))
