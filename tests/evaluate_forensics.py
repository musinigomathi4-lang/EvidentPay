
import csv
import json
import statistics
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

BASELINE_CSV = (
    ROOT_DIR / "storage" / "forensic_results" / "forensic_metrics.csv"
)

BENIGN_JSON = (
    ROOT_DIR / "storage" / "forensic_results"
    / "benign_transformations"
    / "benign_transformation_report.json"
)

OUTPUT = (
    ROOT_DIR / "storage" / "forensic_results"
    / "combined_forensic_evaluation.json"
)

METRICS = {
    "pHash distance": "phash_distance",
    "Edge difference (%)": "edge_difference_percent",
    "Localized difference (%)": "localized_changed_pixel_percent",
    "Detected regions": "regions_detected",
    "Modified ELA mean": "modified_ela_mean",
}


def load_positive_samples():
    samples = []

    with open(BASELINE_CSV, newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            samples.append({
                key: float(row[column])
                for key, column in METRICS.items()
            })

    return samples


def load_negative_samples():
    samples = []

    with open(BENIGN_JSON, encoding="utf-8") as file:
        data = json.load(file)

    for item in data:
        result = item["result"]

        samples.append({
            "pHash distance": float(result["phash_distance"]),
            "Edge difference (%)": float(
                result["edge_analysis"]["edge_difference_percent"]
            ),
            "Localized difference (%)": float(
                result["localized_analysis"]["changed_pixel_percent"]
            ),
            "Detected regions": float(
                result["localized_analysis"]["regions_detected"]
            ),
            "Modified ELA mean": float(
                result["modified_ela"]["mean_difference"]
            ),
        })

    return samples


def get_statistics(values):
    return {
        "min": round(min(values), 4),
        "median": round(statistics.median(values), 4),
        "max": round(max(values), 4),
    }


def main():
    positive = load_positive_samples()
    negative = load_negative_samples()

    print("\n========== DATASET ==========")
    print("Known modified samples:", len(positive))
    print("Benign transformation samples:", len(negative))

    report = {}

    print("\n========== INDICATOR COMPARISON ==========")

    for metric in METRICS:
        positive_values = [x[metric] for x in positive]
        negative_values = [x[metric] for x in negative]

        pos_stats = get_statistics(positive_values)
        neg_stats = get_statistics(negative_values)

        overlap = not (
            max(negative_values) < min(positive_values)
            or max(positive_values) < min(negative_values)
        )

        report[metric] = {
            "modified_screenshots": pos_stats,
            "benign_transformations": neg_stats,
            "ranges_overlap": overlap,
        }

        print(f"\n{metric}")
        print("  Modified:", pos_stats)
        print("  Benign:  ", neg_stats)
        print("  Ranges overlap:", overlap)

    with open(OUTPUT, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    print("\nEvaluation completed.")
    print("Report saved:", OUTPUT)


if __name__ == "__main__":
    main()
