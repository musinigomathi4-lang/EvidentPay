import csv
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output

# Tesseract installation path
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# Screenshot folder
SCREENSHOT_DIR = Path("../uploads/screenshots")

# Output folder
OUTPUT_DIR = Path("ocr_test_results")
OUTPUT_DIR.mkdir(exist_ok=True)

# OCR modes to compare
PSM_MODES = [3, 4, 6, 11, 12]

# Supported image formats
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

results = []

images = [
    file for file in SCREENSHOT_DIR.iterdir()
    if file.suffix.lower() in IMAGE_EXTENSIONS
]

if not images:
    print("No screenshots found!")
    raise SystemExit

for image_path in images:

    print(f"\nTesting: {image_path.name}")

    image = Image.open(image_path)
    image = ImageOps.exif_transpose(image).convert("RGB")

    for psm in PSM_MODES:

        config = f"--psm {psm}"

        text = pytesseract.image_to_string(
            image,
            config=config
        )

        data = pytesseract.image_to_data(
            image,
            config=config,
            output_type=Output.DICT
        )

        confidences = [
            float(conf)
            for conf in data["conf"]
            if conf != "-1" and float(conf) >= 0
        ]

        average_confidence = (
            sum(confidences) / len(confidences)
            if confidences else 0
        )

        output_file = (
            OUTPUT_DIR /
            f"{image_path.stem}_psm_{psm}.txt"
        )

        output_file.write_text(
            text,
            encoding="utf-8"
        )

        results.append({
            "screenshot": image_path.name,
            "psm": psm,
            "average_confidence": round(
                average_confidence, 2
            ),
            "recognized_text": text.replace("\n", " | ")
        })

        print(f"PSM {psm}: confidence = "
              f"{average_confidence:.2f}")

# Save comparison CSV
csv_path = OUTPUT_DIR / "comparison.csv"

with open(csv_path, "w", newline="", encoding="utf-8") as file:

    writer = csv.DictWriter(
        file,
        fieldnames=[
            "screenshot",
            "psm",
            "average_confidence",
            "recognized_text"
        ]
    )

    writer.writeheader()
    writer.writerows(results)

print("\nOCR testing completed!")
print(f"Results saved in: {OUTPUT_DIR.resolve()}")