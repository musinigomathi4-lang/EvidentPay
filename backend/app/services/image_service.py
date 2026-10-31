"""Image helpers: locate the amount row, find the rupee glyph by shape, isolate the digits."""
import re
import cv2
import numpy as np
import pytesseract
from pytesseract import Output


def load_image(path):
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return img


def find_amount_box(img):
    """The amount is the largest text on screen: union of the tallest digit-bearing words."""
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
    if (b > 0).mean() > 0.5:  # text must be the minority colour (handles dark and light themes)
        b = 255 - b
    return b  # text = 255


def looks_like_rupee(comp):
    """Rupee has two horizontal bars in its upper half; digits 2/5/7 have at most one."""
    h, _ = comp.shape
    top = comp[: int(h * 0.55)]
    full_rows = (top > 0).mean(axis=1) > 0.6
    runs = np.diff(np.concatenate([[0], full_rows.astype(int), [0]]))
    return int((runs == 1).sum()) >= 2


def amount_digits_image(img):
    """Return (black-on-white image of the amount digits with the rupee glyph removed, flags)."""
    box = find_amount_box(img)
    if box is None:
        return None, ["no_amount_line"]
    x0, y0, x1, y1 = box
    pad = 12
    # extend left so the rupee glyph is inside the crop even when OCR dropped it
    crop = img[max(y0 - pad, 0): y1 + pad, max(x0 - 90, 0): x1 + pad]
    bw = binarize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))

    n, _, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    comps = [stats[i] for i in range(1, n)
             if stats[i][4] > 40 and stats[i][3] > 0.25 * bw.shape[0]]
    comps.sort(key=lambda s: s[0])
    if len(comps) < 2:
        return None, ["too_few_glyphs"]

    x, y, w, h, _ = comps[0]
    flags = []
    if looks_like_rupee(bw[y:y + h, x:x + w]):
        cut = x + w + 1
    else:
        flags.append("leftmost_glyph_not_rupee")  # never silently strip a real digit
        cut = 0
    return 255 - bw[:, cut:], flags