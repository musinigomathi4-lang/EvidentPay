
import csv
import json
import sys
from pathlib import Path
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.app.services.forensic_service import analyze_screenshot_pair


PAIR_CSV = ROOT_DIR / "data" / "screenshot_pairs.csv"
ORIGINAL_DIR = ROOT_DIR / "uploads" / "screenshots" / "real_ss"

OUTPUT_DIR = ROOT_DIR / "storage" / "forensic_results" / "benign_transformations"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JSON_OUTPUT = OUTPUT_DIR / "benign_transformation_report.json"


def create_transformations(image_path, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as image:
        image = image.convert("RGB")

        transformations = {}

        # 1. JPEG re-save at quality 75
        path = output_dir / "jpeg_quality_75.jpg"
        image.save(path, "JPEG", quality=75)
        transformations["jpeg_quality_75"] = path

        # 2. JPEG re-save at quality 90
        path = output_dir / "jpeg_quality_90.jpg"
        image.save(path, "JPEG", quality=90)
        transformations["jpeg_quality_90"] = path

        # 3. Resize to 80% of original dimensions
        width, height = image.size
        resized = image.resize(
            (int(width * 0.8), int(height * 0.8)),
            Image.Resampling.LANCZOS
        )
        path = output_dir / "resized_80_percent.jpg"
        resized.save(path, "JPEG", quality=90)
        transformations["resized_80_percent"] = path

        # 4. PNG to JPEG conversion
        path = output_dir / "png_to_jpeg.jpg"
        image.save(path, "JPEG", quality=85)
        transformations["png_to_jpeg"] = path

    return transformations


def main():
    all_results = []

    with open(PAIR_CSV, "r", newline="", encoding="utf-8-sig") as file:
        pairs = csv.DictReader(file)

        for index, pair in enumerate(pairs, start=1):
            original_name = pair["original_filename"]
            original_path = ORIGINAL_DIR / original_name

            print(f"\n{'=' * 55}")
            print(f"Original image {index}: {original_name}")

            if not original_path.exists():
                print("Original image missing. Skipping.")
                continue

            transform_dir = OUTPUT_DIR / f"pair_{index}"
            transformations = create_transformations(
                original_path, transform_dir
            )

            for transform_name, transformed_path in transformations.items():
                analysis_dir = transform_dir / f"{transform_name}_analysis"
                analysis_dir.mkdir(parents=True, exist_ok=True)

                result = analyze_screenshot_pair(
                    original_path,
                    transformed_path,
                    analysis_dir
                )

                record = {
                    "pair": index,
                    "original": original_name,
                    "transformation": transform_name,
                    "result": result
                }

                all_results.append(record)

                print(f"\nTransformation: {transform_name}")
                print(json.dumps(result, indent=2, default=str))

    with open(JSON_OUTPUT, "w", encoding="utf-8") as file:
        json.dump(all_results, file, indent=4, default=str)

    print("\nBenign transformation testing completed.")
    print(f"Total comparisons: {len(all_results)}")
    print(f"JSON report: {JSON_OUTPUT}")


if __name__ == "__main__":
    main()
