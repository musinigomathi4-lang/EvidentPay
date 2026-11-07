import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np


# ============================================================
# NOISE ANALYSIS
# ============================================================

def analyze_noise_consistency(
    image_path,
    tile_size=64,
    blur_sigma=1.0,
    flat_threshold=12.0
):
    """
    Estimate local high-frequency noise characteristics.

    This is an experimental statistical analysis.
    It does not independently prove image manipulation.
    """

    image_path = Path(image_path)

    if not image_path.is_file():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)

    if image is None:
        raise ValueError(
            f"Could not read image: {image_path}"
        )

    height, width = image.shape

    if height < tile_size or width < tile_size:
        raise ValueError(
            "Image is too small for the selected tile size."
        )

    gray = image.astype(np.float32)

    # Estimate smooth image content.
    blurred = cv2.GaussianBlur(
        gray,
        (0, 0),
        sigmaX=blur_sigma,
        sigmaY=blur_sigma
    )

    # High-frequency residual.
    residual = gray - blurred

    # Calculate gradients to identify relatively flat areas.
    gradient_x = cv2.Sobel(
        gray,
        cv2.CV_32F,
        1,
        0,
        ksize=3
    )

    gradient_y = cv2.Sobel(
        gray,
        cv2.CV_32F,
        0,
        1,
        ksize=3
    )

    gradient_magnitude = cv2.magnitude(
        gradient_x,
        gradient_y
    )

    # Ignore strong edges/text boundaries.
    flat_mask = gradient_magnitude <= flat_threshold

    flat_residuals = residual[flat_mask]

    if flat_residuals.size == 0:
        raise ValueError(
            "No sufficiently flat regions found."
        )

    global_noise_std = float(
        np.std(flat_residuals)
    )

    global_mean_absolute_residual = float(
        np.mean(np.abs(flat_residuals))
    )

    tile_noise_values = []
    tile_flat_coverage = []

    # Analyze image in local tiles.
    for y in range(0, height, tile_size):

        for x in range(0, width, tile_size):

            y_end = min(
                y + tile_size,
                height
            )

            x_end = min(
                x + tile_size,
                width
            )

            tile_mask = flat_mask[
                y:y_end,
                x:x_end
            ]

            tile_residual = residual[
                y:y_end,
                x:x_end
            ]

            total_pixels = tile_mask.size

            if total_pixels == 0:
                continue

            flat_pixels = int(
                np.count_nonzero(tile_mask)
            )

            flat_fraction = (
                flat_pixels / total_pixels
            )

            # Need enough flat pixels for a reliable estimate.
            if flat_pixels < 50 or flat_fraction < 0.10:
                continue

            selected_residuals = (
                tile_residual[tile_mask]
            )

            tile_noise_std = float(
                np.std(selected_residuals)
            )

            tile_noise_values.append(
                tile_noise_std
            )

            tile_flat_coverage.append(
                flat_fraction
            )

    if not tile_noise_values:
        raise ValueError(
            "Not enough flat image regions for local analysis."
        )

    tile_noise_values = np.array(
        tile_noise_values,
        dtype=np.float32
    )

    median_tile_noise = float(
        np.median(tile_noise_values)
    )

    noise_q1 = float(
        np.percentile(
            tile_noise_values,
            25
        )
    )

    noise_q3 = float(
        np.percentile(
            tile_noise_values,
            75
        )
    )

    noise_iqr = (
        noise_q3 - noise_q1
    )

    # CV can become unstable when the median
    # noise level is very small.
    if median_tile_noise > 0.05:
        noise_cv = float(
            np.std(tile_noise_values)
            / median_tile_noise
        )
    else:
        noise_cv = None

    return {
        "filename": image_path.name,
        "format": image_path.suffix.lower().replace(
            ".",
            ""
        ),
        "width": width,
        "height": height,

        "global_noise_std": round(
            global_noise_std,
            4
        ),

        "mean_absolute_residual": round(
            global_mean_absolute_residual,
            4
        ),

        "median_tile_noise": round(
            median_tile_noise,
            4
        ),

        "noise_q1": round(
            noise_q1,
            4
        ),

        "noise_q3": round(
            noise_q3,
            4
        ),

        "noise_iqr": round(
            noise_iqr,
            4
        ),

        "noise_cv": (
            round(noise_cv, 4)
            if noise_cv is not None
            else None
        ),

        "flat_coverage": round(
            float(np.mean(tile_flat_coverage)),
            4
        ),

        "tiles_analyzed": len(
            tile_noise_values
        )
    }


# ============================================================
# FIND IMAGES
# ============================================================

def get_images(folder):
    """
    Recursively find supported image files.
    """

    supported_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff"
    }

    images = []

    for path in Path(folder).rglob("*"):

        if (
            path.is_file()
            and path.suffix.lower()
            in supported_extensions
        ):
            images.append(path)

    return sorted(images)


# ============================================================
# ANALYZE FOLDER
# ============================================================

def analyze_folder(folder, category):

    folder = Path(folder)

    if not folder.exists():
        print(
            f"\nWARNING: Folder does not exist:"
            f" {folder}"
        )
        return []

    images = get_images(folder)

    print(
        f"\nAnalyzing {category}: "
        f"{len(images)} images"
    )

    results = []

    for index, image_path in enumerate(
        images,
        start=1
    ):

        print(
            f"[{index}/{len(images)}] "
            f"{image_path.name}"
        )

        try:

            result = analyze_noise_consistency(
                image_path
            )

            result["category"] = category

            # Store relative path so we can identify
            # the image later.
            result["relative_path"] = str(
                image_path.relative_to(
                    folder.parent
                )
            )

            results.append(result)

        except Exception as error:

            print(
                f"    ERROR: {error}"
            )

    return results


# ============================================================
# SAVE CSV
# ============================================================

def save_csv(results, output_path):

    if not results:
        return

    fieldnames = [
        "category",
        "filename",
        "relative_path",
        "format",
        "width",
        "height",
        "global_noise_std",
        "mean_absolute_residual",
        "median_tile_noise",
        "noise_q1",
        "noise_q3",
        "noise_iqr",
        "noise_cv",
        "flat_coverage",
        "tiles_analyzed"
    ]

    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(results)

    print(
        f"\nCSV saved to:"
        f" {output_path}"
    )


# ============================================================
# SUMMARY
# ============================================================

def calculate_summary(results):

    categories = sorted(
        set(
            result["category"]
            for result in results
        )
    )

    metrics = [
        "global_noise_std",
        "mean_absolute_residual",
        "median_tile_noise",
        "noise_iqr",
        "noise_cv",
        "flat_coverage"
    ]

    print("\n")
    print("=" * 72)
    print("NOISE ANALYSIS SUMMARY")
    print("=" * 72)

    print(
        f"\nTotal images analyzed: "
        f"{len(results)}"
    )

    for category in categories:

        category_results = [
            result
            for result in results
            if result["category"] == category
        ]

        print(
            f"\n{category.upper()}: "
            f"{len(category_results)} images"
        )

        for metric in metrics:

            values = [
                result[metric]
                for result in category_results
                if result[metric] is not None
            ]

            if not values:
                continue

            values = np.array(
                values,
                dtype=np.float64
            )

            print(
                f"  {metric:<30}"
                f"mean={np.mean(values):.4f}  "
                f"median={np.median(values):.4f}  "
                f"std={np.std(values):.4f}"
            )

    # --------------------------------------------------------
    # Compare category means
    # --------------------------------------------------------

    if (
        "genuine" in categories
        and "modified" in categories
    ):

        genuine = [
            result
            for result in results
            if result["category"] == "genuine"
        ]

        modified = [
            result
            for result in results
            if result["category"] == "modified"
        ]

        print("\n")
        print("-" * 72)
        print("GENUINE vs MODIFIED")
        print("-" * 72)

        for metric in metrics:

            genuine_values = [
                result[metric]
                for result in genuine
                if result[metric] is not None
            ]

            modified_values = [
                result[metric]
                for result in modified
                if result[metric] is not None
            ]

            if (
                not genuine_values
                or not modified_values
            ):
                continue

            genuine_mean = np.mean(
                genuine_values
            )

            modified_mean = np.mean(
                modified_values
            )

            if genuine_mean != 0:

                percentage_difference = (
                    (
                        modified_mean
                        - genuine_mean
                    )
                    / abs(genuine_mean)
                ) * 100

            else:
                percentage_difference = 0

            print(
                f"\n{metric}"
            )

            print(
                f"  Genuine mean:  "
                f"{genuine_mean:.4f}"
            )

            print(
                f"  Modified mean: "
                f"{modified_mean:.4f}"
            )

            print(
                f"  Difference:     "
                f"{percentage_difference:+.2f}%"
            )

    print("\n")
    print("=" * 72)


# ============================================================
# MAIN
# ============================================================

def main():

    # uploads is OUTSIDE backend.
    # test_noise.py is inside backend.
    project_root = Path(__file__).parent.parent

    screenshots_root = (
        project_root
        / "uploads"
        / "screenshots"
    )

    # Allow a custom dataset folder from command line.
    if len(sys.argv) >= 2:
        screenshots_root = Path(sys.argv[1])

    genuine_folder = (
        screenshots_root
        / "real_ss"
    )

    modified_folder = (
        screenshots_root
        / "fake_ss"
    )

    print("=" * 72)
    print("EVIDENTPAY - BATCH NOISE ANALYSIS")
    print("=" * 72)

    print(
        f"\nDataset:"
        f" {screenshots_root}"
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
        print(
            "\nNo images were found."
        )
        return

    # Save CSV next to this test script.
    output_path = (
        Path(__file__).parent
        / "noise_results.csv"
    )

    save_csv(
        results,
        output_path
    )

    calculate_summary(
        results
    )

    # Also save JSON for future analysis.
    json_path = (
        Path(__file__).parent
        / "noise_results.json"
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

    print(
        f"\nJSON saved to:"
        f" {json_path}"
    )


if __name__ == "__main__":
    main()