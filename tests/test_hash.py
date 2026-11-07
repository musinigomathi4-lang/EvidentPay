
import csv
import hashlib
from pathlib import Path
from collections import defaultdict

ROOT_DIR = Path(__file__).resolve().parents[1]

PAIR_CSV = ROOT_DIR / "data" / "screenshot_pairs.csv"
ORIGINAL_DIR = ROOT_DIR / "uploads" / "screenshots" / "real_ss"
MODIFIED_DIR = ROOT_DIR / "uploads" / "screenshots" / "fake_ss"

OUTPUT_DIR = ROOT_DIR / "storage" / "forensic_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CSV_OUTPUT = OUTPUT_DIR / "hash_metrics.csv"


def calculate_sha256(image_path):
    """Calculate the SHA-256 hash of an image file."""
    sha256 = hashlib.sha256()

    with open(image_path, "rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def main():
    results = []
    hash_groups = defaultdict(list)

    with open(PAIR_CSV, "r", newline="", encoding="utf-8-sig") as file:
        pairs = csv.DictReader(file)

        for index, pair in enumerate(pairs, start=1):
            original_name = pair["original_filename"]
            modified_name = pair["modified_filename"]

            original_path = ORIGINAL_DIR / original_name
            modified_path = MODIFIED_DIR / modified_name

            if not original_path.exists() or not modified_path.exists():
                print(f"Pair {index}: Missing image. Skipping.")
                continue

            original_hash = calculate_sha256(original_path)
            modified_hash = calculate_sha256(modified_path)

            identical = original_hash == modified_hash

            print(f"\nPair {index}: {original_name} -> {modified_name}")
            print(f"Original SHA-256: {original_hash}")
            print(f"Modified SHA-256: {modified_hash}")
            print(f"Exact duplicate: {identical}")

            hash_groups[original_hash].append(original_name)
            hash_groups[modified_hash].append(modified_name)

            results.append({
                "pair": index,
                "original": original_name,
                "modified": modified_name,
                "original_hash": original_hash,
                "modified_hash": modified_hash,
                "exact_duplicate": identical
            })

    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow([
            "pair",
            "original",
            "modified",
            "original_sha256",
            "modified_sha256",
            "exact_duplicate"
        ])

        for result in results:
            writer.writerow([
                result["pair"],
                result["original"],
                result["modified"],
                result["original_hash"],
                result["modified_hash"],
                result["exact_duplicate"]
            ])

    duplicate_groups = [
        filenames
        for filenames in hash_groups.values()
        if len(filenames) > 1
    ]

    print("\n========== SUMMARY ==========")
    print(f"Pairs analysed: {len(results)}")
    print(
        "Original-modified exact matches:",
        sum(result["exact_duplicate"] for result in results)
    )
    print(f"Duplicate groups across dataset: {len(duplicate_groups)}")

    for group in duplicate_groups:
        print("Duplicate files:", ", ".join(group))

    print(f"\nCSV report: {CSV_OUTPUT}")


if __name__ == "__main__":
    main()
