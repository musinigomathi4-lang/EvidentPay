
import csv
from pathlib import Path
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parents[1]

PAIR_CSV = ROOT_DIR / "data" / "screenshot_pairs.csv"
ORIGINAL_DIR = ROOT_DIR / "uploads" / "screenshots" / "real_ss"
MODIFIED_DIR = ROOT_DIR / "uploads" / "screenshots" / "fake_ss"

OUTPUT_DIR = ROOT_DIR / "storage" / "forensic_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CSV_OUTPUT = OUTPUT_DIR / "compression_metrics.csv"


def analyze_compression(image_path):
    with Image.open(image_path) as image:
        quantization = image.quantization

        if not quantization:
            return {
                "format": image.format,
                "available": False,
                "tables": {},
            }

        return {
            "format": image.format,
            "available": True,
            "tables": quantization,
        }

def analyze_compression(image_path):
    with Image.open(image_path) as image:

        if image.format != "JPEG":
            return {
                "format": image.format,
                "available": False,
                "tables": {},
            }

        quantization = image.quantization

        return {
            "format": image.format,
            "available": bool(quantization),
            "tables": quantization or {},
        }


def compare_tables(original, modified):
    if not original["available"] or not modified["available"]:
        return {
            "comparable": False,
            "identical": None,
            "changed_values": None,
            "total_values": None,
            "difference_percentage": None,
        }

    original_tables = original["tables"]
    modified_tables = modified["tables"]

    if original_tables.keys() != modified_tables.keys():
        return {
            "comparable": False,
            "identical": False,
            "changed_values": None,
            "total_values": None,
            "difference_percentage": None,
        }

    changed = 0
    total = 0

    for table_id in original_tables:
        first = original_tables[table_id]
        second = modified_tables[table_id]

        if len(first) != len(second):
            return {
                "comparable": False,
                "identical": False,
                "changed_values": None,
                "total_values": None,
                "difference_percentage": None,
            }

        for a, b in zip(first, second):
            total += 1

            if a != b:
                changed += 1

    return {
        "comparable": True,
        "identical": changed == 0,
        "changed_values": changed,
        "total_values": total,
        "difference_percentage": (
            round((changed / total) * 100, 2) if total else 0
        ),
    }


def main():
    results = []

    with open(PAIR_CSV, "r", newline="", encoding="utf-8-sig") as file:
        pairs = csv.DictReader(file)

        for index, pair in enumerate(pairs, start=1):
            original_name = pair["original_filename"]
            modified_name = pair["modified_filename"]

            original_path = ORIGINAL_DIR / original_name
            modified_path = MODIFIED_DIR / modified_name

            original = analyze_compression(original_path)
            modified = analyze_compression(modified_path)

            comparison = compare_tables(original, modified)

            print(f"\nPair {index}: {original_name} -> {modified_name}")
            print(f"Formats: {original['format']} -> {modified['format']}")
            print(
                f"Quantization tables available: "
                f"{original['available']} -> {modified['available']}"
            )

            if comparison["comparable"]:
                print(f"Tables identical: {comparison['identical']}")
                print(
                    f"Changed values: {comparison['changed_values']} / "
                    f"{comparison['total_values']}"
                )
                print(
                    f"Difference percentage: "
                    f"{comparison['difference_percentage']}%"
                )
            else:
                print("Quantization tables cannot be compared.")

            results.append({
                "pair": index,
                "original": original_name,
                "modified": modified_name,
                "original_format": original["format"],
                "modified_format": modified["format"],
                "original_tables_available": original["available"],
                "modified_tables_available": modified["available"],
                **comparison,
            })

    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print("\nCompression analysis completed.")
    print(f"CSV report: {CSV_OUTPUT}")


if __name__ == "__main__":
    main()
