
import csv
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.app.services.metadata_service import analyze_image_metadata


PAIR_CSV = ROOT_DIR / "data" / "screenshot_pairs.csv"

ORIGINAL_DIR = ROOT_DIR / "uploads" / "screenshots" / "real_ss"
MODIFIED_DIR = ROOT_DIR / "uploads" / "screenshots" / "fake_ss"

OUTPUT_DIR = ROOT_DIR / "storage" / "forensic_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JSON_OUTPUT = OUTPUT_DIR / "metadata_report.json"
CSV_OUTPUT = OUTPUT_DIR / "metadata_metrics.csv"


def main():
    results = []

    with open(PAIR_CSV, "r", newline="", encoding="utf-8-sig") as file:
        pairs = csv.DictReader(file)

        for index, pair in enumerate(pairs, start=1):
            original_name = pair["original_filename"]
            modified_name = pair["modified_filename"]

            original_path = ORIGINAL_DIR / original_name
            modified_path = MODIFIED_DIR / modified_name

            print(f"\nPair {index}: {original_name} -> {modified_name}")

            original = analyze_image_metadata(original_path)
            modified = analyze_image_metadata(modified_path)

            print(
                f"Format: {original['format']} -> {modified['format']}"
            )

            print(
                f"Dimensions: {original['dimensions']} -> "
                f"{modified['dimensions']}"
            )

            print(
                f"File size: {original['file_size_bytes']} -> "
                f"{modified['file_size_bytes']} bytes"
            )

            print(
                f"Software: {original['software']} -> "
                f"{modified['software']}"
            )

            print(
                f"Editor keywords: "
                f"{original['detected_editor_keywords']} -> "
                f"{modified['detected_editor_keywords']}"
            )

            print(
                f"ICC profile: {original['has_icc_profile']} -> "
                f"{modified['has_icc_profile']}"
            )

            results.append({
                "pair": index,
                "original": original,
                "modified": modified
            })

    with open(JSON_OUTPUT, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4)

    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow([
            "pair",
            "original",
            "modified",
            "original_format",
            "modified_format",
            "original_width",
            "original_height",
            "modified_width",
            "modified_height",
            "original_size_bytes",
            "modified_size_bytes",
            "original_software",
            "modified_software",
            "original_editors",
            "modified_editors",
            "original_icc",
            "modified_icc",
            "original_exif_count",
            "modified_exif_count"
        ])

        for result in results:
            original = result["original"]
            modified = result["modified"]

            writer.writerow([
                result["pair"],
                original["filename"],
                modified["filename"],
                original["format"],
                modified["format"],
                original["dimensions"]["width"],
                original["dimensions"]["height"],
                modified["dimensions"]["width"],
                modified["dimensions"]["height"],
                original["file_size_bytes"],
                modified["file_size_bytes"],
                original["software"],
                modified["software"],
                ", ".join(original["detected_editor_keywords"]),
                ", ".join(modified["detected_editor_keywords"]),
                original["has_icc_profile"],
                modified["has_icc_profile"],
                len(original["exif"]),
                len(modified["exif"])
            ])

    print("\nMetadata analysis completed.")
    print(f"JSON report: {JSON_OUTPUT}")
    print(f"CSV report: {CSV_OUTPUT}")


if __name__ == "__main__":
    main()
