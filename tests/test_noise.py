
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.noise_service import analyze_noise_consistency


PAIR_CSV = PROJECT_ROOT / "data" / "screenshot_pairs.csv"
ORIGINAL_DIR = PROJECT_ROOT / "uploads" / "screenshots" / "real_ss"
MODIFIED_DIR = PROJECT_ROOT / "uploads" / "screenshots" / "fake_ss"


METRIC_KEYS = [
    "global_flat_region_noise_std",
    "global_mean_absolute_residual",
    "median_tile_noise_std",
    "tile_noise_iqr",
    "tile_noise_coefficient_of_variation",
    "average_flat_pixel_coverage",
    "tiles_analyzed",
]


def main():
    with open(PAIR_CSV, "r", encoding="utf-8-sig") as file:
        pairs = list(csv.DictReader(file))

    results = []

    print("\n========== NOISE ANALYSIS ==========\n")

    for index, pair in enumerate(pairs, start=1):
        original_name = pair["original_filename"]
        modified_name = pair["modified_filename"]

        original_path = ORIGINAL_DIR / original_name
        modified_path = MODIFIED_DIR / modified_name

        print(
            f"Pair {index}/{len(pairs)}: "
            f"{original_name} -> {modified_name}"
        )

        try:
            original = analyze_noise_consistency(original_path)
            modified = analyze_noise_consistency(modified_path)

            original_metrics = original["metrics"]
            modified_metrics = modified["metrics"]

            result = {
                "pair": index,
                "original": original_name,
                "modified": modified_name,
            }

            for key in METRIC_KEYS:
                original_value = original_metrics[key]
                modified_value = modified_metrics[key]

                if original_value is not None and original_value != 0:
                    change = (
                        (modified_value - original_value)
                        / abs(original_value)
                    ) * 100
                else:
                    change = None

                result[f"original_{key}"] = original_value
                result[f"modified_{key}"] = modified_value
                result[f"{key}_change_percent"] = (
                    round(change, 2) if change is not None else None
                )

                print(
                    f"  {key}: "
                    f"{original_value} -> {modified_value} "
                    f"({change:+.2f}%)"
                    if change is not None
                    else f"  {key}: {original_value} -> {modified_value}"
                )

            results.append(result)

        except (FileNotFoundError, ValueError) as error:
            print(f"  SKIPPED: {error}")

        print()

    if results:
        output_path = PROJECT_ROOT / "storage" / "forensic_results"
        output_path.mkdir(parents=True, exist_ok=True)

        report_path = output_path / "noise_metrics.csv"

        with open(report_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=results[0].keys()
            )
            writer.writeheader()
            writer.writerows(results)

        print(f"Analysis complete. Pairs analysed: {len(results)}")
        print(f"CSV report: {report_path}")
    else:
        print("No pairs could be analysed.")


if __name__ == "__main__":
    main()
