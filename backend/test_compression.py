
import csv
import json
import hashlib
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


PROJECT_ROOT = Path(__file__).parent.parent
SCREENSHOTS_ROOT = PROJECT_ROOT / "uploads" / "screenshots"

SUPPORTED_FORMATS = {
    ".jpg",
    ".jpeg",
    ".png"
}


def analyze_compression(image_path):

    image = Image.open(image_path)

    result = {
        "filename": image_path.name,
        "format": image.format,
        "width": image.width,
        "height": image.height,
        "file_size_bytes": image_path.stat().st_size,
        "quantization_table_count": 0,
        "quantization_fingerprint": None,
        "quantization_mean": None,
        "quantization_std": None,
        "blockiness_score": None,
        "blockiness_normalized": None
    }

    # --------------------------------------------------
    # 1. JPEG QUANTIZATION TABLE ANALYSIS
    # --------------------------------------------------

    quantization = getattr(
        image,
        "quantization",
        None
    )

    if quantization:

        tables = []

        for table_id in sorted(quantization):

            table = np.array(
                quantization[table_id],
                dtype=np.float64
            )

            tables.extend(table.tolist())

        table_array = np.array(
            tables,
            dtype=np.float64
        )

        fingerprint_data = json.dumps(
            {
                str(key): quantization[key]
                for key in sorted(quantization)
            },
            sort_keys=True
        )

        fingerprint = hashlib.sha256(
            fingerprint_data.encode()
        ).hexdigest()[:16]

        result["quantization_table_count"] = len(
            quantization
        )

        result["quantization_fingerprint"] = fingerprint

        result["quantization_mean"] = round(
            float(np.mean(table_array)),
            4
        )

        result["quantization_std"] = round(
            float(np.std(table_array)),
            4
        )

    # --------------------------------------------------
    # 2. JPEG 8x8 BLOCK BOUNDARY ANALYSIS
    # --------------------------------------------------

    if image.format == "JPEG":

        gray = cv2.imread(
            str(image_path),
            cv2.IMREAD_GRAYSCALE
        )

        if gray is not None:

            gray = gray.astype(
                np.float32
            )

            # Differences across horizontal boundaries
            vertical_differences = np.abs(
                np.diff(gray, axis=0)
            )

            # Differences across vertical boundaries
            horizontal_differences = np.abs(
                np.diff(gray, axis=1)
            )

            # Boundaries at multiples of 8
            vertical_boundary = np.mean(
                vertical_differences[7::8, :]
            )

            vertical_non_boundary = np.mean(
                vertical_differences[
                    np.arange(
                        vertical_differences.shape[0]
                    ) % 8 != 7
                ]
            )

            horizontal_boundary = np.mean(
                horizontal_differences[:, 7::8]
            )

            horizontal_non_boundary = np.mean(
                horizontal_differences[
                    :,
                    np.arange(
                        horizontal_differences.shape[1]
                    ) % 8 != 7
                ]
            )

            boundary_score = (
                vertical_boundary
                + horizontal_boundary
            ) / 2

            non_boundary_score = (
                vertical_non_boundary
                + horizontal_non_boundary
            ) / 2

            result["blockiness_score"] = round(
                float(boundary_score),
                6
            )

            result["blockiness_normalized"] = round(
                float(
                    boundary_score
                    / (non_boundary_score + 1e-8)
                ),
                6
            )

    image.close()

    return result


def get_images(folder):

    if not folder.exists():
        return []

    return sorted(
        [
            path
            for path in folder.rglob("*")
            if path.suffix.lower() in SUPPORTED_FORMATS
        ]
    )


def analyze_folder(folder, category):

    images = get_images(folder)

    print(
        f"\nAnalyzing {category}: {len(images)} images"
    )

    results = []

    for index, image_path in enumerate(images, 1):

        print(
            f"[{index}/{len(images)}] {image_path.name}"
        )

        try:

            result = analyze_compression(
                image_path
            )

            result["category"] = category

            results.append(result)

        except Exception as error:

            print(
                f"ERROR: {image_path.name}: {error}"
            )

    return results


def save_csv(results, output_path):

    if not results:
        return

    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=results[0].keys()
        )

        writer.writeheader()
        writer.writerows(results)

    print(
        f"\nCSV saved to: {output_path}"
    )


def print_summary(results):

    print("\n")
    print("=" * 72)
    print("COMPRESSION ANALYSIS SUMMARY")
    print("=" * 72)

    for category in ["genuine", "modified"]:

        group = [
            item
            for item in results
            if item["category"] == category
            and item["format"] == "JPEG"
        ]

        print(
            f"\n{category.upper()}: {len(group)} JPEG images"
        )

        if not group:
            continue

        metrics = [
            "quantization_mean",
            "quantization_std",
            "blockiness_score",
            "blockiness_normalized"
        ]

        for metric in metrics:

            values = [
                item[metric]
                for item in group
                if item[metric] is not None
            ]

            if not values:
                continue

            print(
                f"  {metric:28}"
                f" mean={np.mean(values):.6f}"
                f" median={np.median(values):.6f}"
                f" std={np.std(values):.6f}"
            )

        fingerprints = {}

        for item in group:

            fingerprint = item[
                "quantization_fingerprint"
            ]

            if fingerprint:

                fingerprints[fingerprint] = (
                    fingerprints.get(
                        fingerprint,
                        0
                    ) + 1
                )

        print(
            f"  Unique quantization tables: "
            f"{len(fingerprints)}"
        )

    print("\n")
    print("=" * 72)
    print("QUANTIZATION TABLE COMPARISON")
    print("=" * 72)

    for category in ["genuine", "modified"]:

        group = [
            item
            for item in results
            if item["category"] == category
            and item["format"] == "JPEG"
        ]

        fingerprints = [
            item["quantization_fingerprint"]
            for item in group
            if item["quantization_fingerprint"]
        ]

        print(
            f"{category.capitalize()}: "
            f"{len(set(fingerprints))} unique fingerprints"
        )

    png_count = sum(
        1
        for item in results
        if item["format"] == "PNG"
    )

    print(
        f"\nPNG images analyzed separately: {png_count}"
    )


def main():

    genuine_folder = (
        SCREENSHOTS_ROOT / "real_ss"
    )

    modified_folder = (
        SCREENSHOTS_ROOT / "fake_ss"
    )

    print("=" * 72)
    print("EVIDENTPAY - BATCH COMPRESSION ANALYSIS")
    print("=" * 72)

    print(
        f"\nDataset: {SCREENSHOTS_ROOT}"
    )

    genuine_results = analyze_folder(
        genuine_folder,
        "genuine"
    )

    modified_results = analyze_folder(
        modified_folder,
        "modified"
    )

    results = (
        genuine_results
        + modified_results
    )

    if not results:

        print("\nNo images found.")
        return

    output_path = (
        Path(__file__).parent
        / "compression_results.csv"
    )

    save_csv(
        results,
        output_path
    )

    json_path = (
        Path(__file__).parent
        / "compression_results.json"
    )

    with open(
        json_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=4
        )

    print_summary(results)

    print(
        f"\nJSON saved to: {json_path}"
    )


if __name__ == "__main__":
    main()
