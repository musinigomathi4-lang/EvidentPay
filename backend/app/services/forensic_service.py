
from pathlib import Path

import cv2
import imagehash
import numpy as np

from PIL import Image, ImageChops, ImageEnhance
from skimage.metrics import structural_similarity


def calculate_phash_distance(original_path, modified_path):
    with Image.open(original_path) as original:
        original_hash = imagehash.phash(original.convert("RGB"))

    with Image.open(modified_path) as modified:
        modified_hash = imagehash.phash(modified.convert("RGB"))

    return int(original_hash - modified_hash)


def create_ela_image(image_path, output_path, quality=90):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as image:
        image = image.convert("RGB")

        temporary_path = output_path.with_name(
            f"{output_path.stem}_temporary.jpg"
        )

        image.save(temporary_path, "JPEG", quality=quality)

        with Image.open(temporary_path) as recompressed:
            difference = ImageChops.difference(image, recompressed)

        temporary_path.unlink(missing_ok=True)

    difference_array = np.asarray(difference, dtype=np.float32)

    mean_difference = float(difference_array.mean())
    max_difference = int(difference_array.max())

    enhanced = ImageEnhance.Brightness(difference).enhance(10)
    enhanced.save(output_path)

    return {
        "mean_difference": round(mean_difference, 3),
        "max_difference": max_difference,
        "output_image": str(output_path)
    }


def compare_edges(original_path, modified_path, output_path):
    original = cv2.imread(str(original_path))
    modified = cv2.imread(str(modified_path))

    if original is None or modified is None:
        raise ValueError("Could not read one of the images.")

    height, width = original.shape[:2]
    modified = cv2.resize(modified, (width, height))

    original_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
    modified_gray = cv2.cvtColor(modified, cv2.COLOR_BGR2GRAY)

    original_edges = cv2.Canny(original_gray, 100, 200)
    modified_edges = cv2.Canny(modified_gray, 100, 200)

    edge_difference = cv2.bitwise_xor(
        original_edges,
        modified_edges
    )

    changed_pixels = int(np.count_nonzero(edge_difference))
    total_pixels = height * width

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(output_path), edge_difference)

    return {
        "changed_edge_pixels": changed_pixels,
        "edge_difference_percent": round(
            changed_pixels / total_pixels * 100, 3
        ),
        "output_image": str(output_path)
    }


def compare_local_regions(original_path, modified_path, output_dir):
    """
    Detect localized differences between a known original and modified pair.

    This is a reference-based comparison, not a standalone fake detector.
    """
    original = cv2.imread(str(original_path))
    modified = cv2.imread(str(modified_path))

    if original is None or modified is None:
        raise ValueError("Could not read one of the images.")

    height, width = original.shape[:2]

    original_ratio = width / height
    modified_ratio = modified.shape[1] / modified.shape[0]

    if abs(original_ratio - modified_ratio) > 0.01:
        raise ValueError(
            "Image aspect ratios differ significantly. "
            "Automatic resizing may misalign the comparison."
        )

    modified = cv2.resize(modified, (width, height))

    original_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
    modified_gray = cv2.cvtColor(modified, cv2.COLOR_BGR2GRAY)

    _, similarity_map = structural_similarity(
        original_gray,
        modified_gray,
        full=True,
        data_range=255
    )

    difference_map = 1.0 - similarity_map
    difference_image = np.clip(
        difference_map * 255, 0, 255
    ).astype(np.uint8)

    # Threshold creates candidate changed regions.
    _, threshold_map = cv2.threshold(
        difference_image,
        30,
        255,
        cv2.THRESH_BINARY
    )

    # Remove tiny isolated noise and join nearby changed pixels.
    kernel = np.ones((3, 3), np.uint8)

    cleaned = cv2.morphologyEx(
        threshold_map,
        cv2.MORPH_OPEN,
        kernel
    )

    cleaned = cv2.dilate(cleaned, kernel, iterations=1)

    contours, _ = cv2.findContours(
        cleaned,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    regions = []
    annotated = modified.copy()

    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        area = box_width * box_height

        # Ignore extremely small regions.
        if area < 20:
            continue

        region_difference = difference_map[
            y:y + box_height,
            x:x + box_width
        ]

        regions.append({
            "x": int(x),
            "y": int(y),
            "width": int(box_width),
            "height": int(box_height),
            "area": int(area),
            "mean_difference": round(
                float(region_difference.mean()), 4
            )
        })

        cv2.rectangle(
            annotated,
            (x, y),
            (x + box_width, y + box_height),
            (0, 0, 255),
            2
        )

    regions.sort(
        key=lambda region: region["area"],
        reverse=True
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pair_name = Path(modified_path).stem

    annotated_path = output_dir / f"{pair_name}_localized.png"
    heatmap_path = output_dir / f"{pair_name}_ssim_heatmap.png"

    heatmap = cv2.applyColorMap(
        difference_image,
        cv2.COLORMAP_JET
    )

    cv2.imwrite(str(annotated_path), annotated)
    cv2.imwrite(str(heatmap_path), heatmap)

    changed_pixel_percent = (
        np.count_nonzero(threshold_map) /
        (height * width)
    ) * 100

    return {
        "changed_pixel_percent": round(
            changed_pixel_percent, 3
        ),
        "regions_detected": len(regions),
        "regions": regions,
        "annotated_image": str(annotated_path),
        "heatmap_image": str(heatmap_path)
    }


def analyze_screenshot_pair(original_path, modified_path, output_dir):
    original_path = Path(original_path)
    modified_path = Path(modified_path)
    output_dir = Path(output_dir)

    if not original_path.is_file():
        raise FileNotFoundError(
            f"Original screenshot not found: {original_path}"
        )

    if not modified_path.is_file():
        raise FileNotFoundError(
            f"Modified screenshot not found: {modified_path}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    pair_name = modified_path.stem

    phash_distance = calculate_phash_distance(
        original_path,
        modified_path
    )

    original_ela = create_ela_image(
        original_path,
        output_dir / f"{pair_name}_original_ela.png"
    )

    modified_ela = create_ela_image(
        modified_path,
        output_dir / f"{pair_name}_modified_ela.png"
    )

    edge_result = compare_edges(
        original_path,
        modified_path,
        output_dir / f"{pair_name}_edge_difference.png"
    )

    localized_result = compare_local_regions(
        original_path,
        modified_path,
        output_dir
    )

    return {
        "original_filename": original_path.name,
        "modified_filename": modified_path.name,
        "phash_distance": phash_distance,
        "original_ela": original_ela,
        "modified_ela": modified_ela,
        "edge_analysis": edge_result,
        "localized_analysis": localized_result,
        "interpretation": (
            "Comparison indicators require manual review. "
            "They do not independently establish image authenticity."
        )
    }
