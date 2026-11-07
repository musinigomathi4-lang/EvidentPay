
import json
import csv
from pathlib import Path
from collections import defaultdict

ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT = (
    ROOT_DIR / "storage" / "forensic_results"
    / "benign_transformations"
    / "benign_transformation_report.json"
)

OUTPUT = (
    ROOT_DIR / "storage" / "forensic_results"
    / "benign_transformation_summary.csv"
)


def main():
    with open(INPUT, "r", encoding="utf-8") as file:
        data = json.load(file)

    rows = []
    grouped = defaultdict(list)

    for item in data:
        result = item["result"]
        edge = result["edge_analysis"]
        localized = result["localized_analysis"]

        row = {
            "pair": item["pair"],
            "transformation": item["transformation"],
            "phash_distance": result["phash_distance"],
            "ela_original_mean": result["original_ela"]["mean_difference"],
            "ela_modified_mean": result["modified_ela"]["mean_difference"],
            "edge_difference_percent": edge["edge_difference_percent"],
            "changed_pixel_percent": localized["changed_pixel_percent"],
            "regions_detected": localized["regions_detected"],
        }

        rows.append(row)
        grouped[item["transformation"]].append(row)

    with open(OUTPUT, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print("\n========== TRANSFORMATION SUMMARY ==========")

    print(
        f"{'Transformation':<24}"
        f"{'Avg pHash':<12}"
        f"{'Avg Edge %':<13}"
        f"{'Avg Local %':<14}"
        f"{'Avg Regions':<13}"
    )

    print("-" * 76)

    for name, group in grouped.items():
        count = len(group)

        avg_phash = sum(
            x["phash_distance"] for x in group
        ) / count

        avg_edge = sum(
            x["edge_difference_percent"] for x in group
        ) / count

        avg_local = sum(
            x["changed_pixel_percent"] for x in group
        ) / count

        avg_regions = sum(
            x["regions_detected"] for x in group
        ) / count

        print(
            f"{name:<24}"
            f"{avg_phash:<12.2f}"
            f"{avg_edge:<13.3f}"
            f"{avg_local:<14.3f}"
            f"{avg_regions:<13.2f}"
        )

    print("\nTotal comparisons:", len(rows))
    print("CSV saved:", OUTPUT)


if __name__ == "__main__":
    main()
