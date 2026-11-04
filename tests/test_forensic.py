
import csv
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"

sys.path.insert(0, str(BACKEND_DIR))

from app.services.forensic_service import analyze_screenshot_pair


MAPPING_FILE = ROOT_DIR / "data" / "screenshot_pairs.csv"
ORIGINAL_DIR = ROOT_DIR / "uploads" / "screenshots" / "real_ss"
MODIFIED_DIR = ROOT_DIR / "uploads" / "screenshots" / "fake_ss"
OUTPUT_DIR = ROOT_DIR / "storage" / "forensic_results"


def main():
    if not MAPPING_FILE.is_file():
        raise FileNotFoundError(
            f"Mapping CSV not found: {MAPPING_FILE}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(MAPPING_FILE, "r", newline="", encoding="utf-8-sig") as file:
        pairs = list(csv.DictReader(file))

    if not pairs:
        raise ValueError("The mapping CSV has no data rows.")

    required_columns = {
        "original_filename",
        "modified_filename"
    }

    actual_columns = set(pairs[0].keys())

    if not required_columns.issubset(actual_columns):
        raise ValueError(
            "CSV must contain these columns: "
            "original_filename, modified_filename"
        )

    results = []

    for index, pair in enumerate(pairs, start=1):
        original_filename = pair["original_filename"].strip()
        modified_filename = pair["modified_filename"].strip()

        if not original_filename or not modified_filename:
            print(f"Skipping pair {index}: missing filename.")
            continue

        original_path = ORIGINAL_DIR / original_filename
        modified_path = MODIFIED_DIR / modified_filename

        print(
            f"\nAnalysing pair {index}/{len(pairs)}: "
            f"{original_filename} -> {modified_filename}"
        )

        try:
            result = analyze_screenshot_pair(
                original_path,
                modified_path,
                OUTPUT_DIR
            )

            results.append(result)

            localized = result["localized_analysis"]

            print(f"pHash distance: {result['phash_distance']}")

            print(
                "Edge difference: "
                f"{result['edge_analysis']['edge_difference_percent']}%"
            )

            print(
                "Localized changed pixels: "
                f"{localized['changed_pixel_percent']}%"
            )

            print(
                "Regions detected: "
                f"{localized['regions_detected']}"
            )

        except Exception as error:
            print(f"Pair {index} failed: {error}")

    report_path = OUTPUT_DIR / "forensic_report.json"

    with open(report_path, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4)

    csv_path = OUTPUT_DIR / "forensic_metrics.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "original_filename",
                "modified_filename",
                "phash_distance",
                "original_ela_mean",
                "modified_ela_mean",
                "edge_difference_percent",
                "localized_changed_pixel_percent",
                "regions_detected"
            ]
        )

        writer.writeheader()

        for result in results:
            localized = result["localized_analysis"]

            writer.writerow({
                "original_filename": result["original_filename"],
                "modified_filename": result["modified_filename"],
                "phash_distance": result["phash_distance"],
                "original_ela_mean": (
                    result["original_ela"]["mean_difference"]
                ),
                "modified_ela_mean": (
                    result["modified_ela"]["mean_difference"]
                ),
                "edge_difference_percent": (
                    result["edge_analysis"]["edge_difference_percent"]
                ),
                "localized_changed_pixel_percent": (
                    localized["changed_pixel_percent"]
                ),
                "regions_detected": localized["regions_detected"]
            })

    print("\nAnalysis complete.")
    print(f"Pairs analysed: {len(results)}")
    print(f"JSON report: {report_path}")
    print(f"CSV report: {csv_path}")
    print(f"Visual outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
