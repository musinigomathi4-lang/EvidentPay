
from pathlib import Path

import cv2
import numpy as np


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
        raise ValueError("Could not read image.")

    height, width = image.shape

    if height < tile_size or width < tile_size:
        raise ValueError(
            "Image is too small for the selected tile size."
        )

    # Convert to float for accurate residual calculations.
    gray = image.astype(np.float32)

    # Estimate the smooth image content.
    blurred = cv2.GaussianBlur(
        gray,
        (0, 0),
        sigmaX=blur_sigma,
        sigmaY=blur_sigma
    )

    # High-frequency residual: details not explained by the blur.
    residual = gray - blurred

    # Calculate image gradients to identify relatively flat areas.
    gradient_x = cv2.Sobel(
        gray, cv2.CV_32F, 1, 0, ksize=3
    )

    gradient_y = cv2.Sobel(
        gray, cv2.CV_32F, 0, 1, ksize=3
    )

    gradient_magnitude = cv2.magnitude(
        gradient_x,
        gradient_y
    )

    # Exclude strong edges and text boundaries from noise estimates.
    flat_mask = gradient_magnitude <= flat_threshold

    flat_residuals = residual[flat_mask]

    if flat_residuals.size == 0:
        raise ValueError(
            "No sufficiently flat regions found."
        )

    global_noise_std = float(np.std(flat_residuals))
    global_mean_absolute_residual = float(
        np.mean(np.abs(flat_residuals))
    )

    tile_noise_values = []
    tile_flat_coverage = []

    # Divide the image into smaller regions.
    for y in range(0, height, tile_size):
        for x in range(0, width, tile_size):

            y_end = min(y + tile_size, height)
            x_end = min(x + tile_size, width)

            tile_mask = flat_mask[y:y_end, x:x_end]
            tile_residual = residual[y:y_end, x:x_end]

            total_pixels = tile_mask.size
            flat_pixels = int(np.count_nonzero(tile_mask))

            if total_pixels == 0:
                continue

            flat_fraction = flat_pixels / total_pixels

            # Ignore tiles with too few usable flat pixels.
            if flat_pixels < 50 or flat_fraction < 0.10:
                continue

            selected_residuals = tile_residual[tile_mask]

            tile_noise_std = float(
                np.std(selected_residuals)
            )

            tile_noise_values.append(tile_noise_std)
            tile_flat_coverage.append(flat_fraction)

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
        np.percentile(tile_noise_values, 25)
    )

    noise_q3 = float(
        np.percentile(tile_noise_values, 75)
    )

    noise_iqr = noise_q3 - noise_q1

    noise_cv = (
        float(np.std(tile_noise_values) / median_tile_noise)
        if median_tile_noise > 0
        else None
    )

    return {
        "filename": image_path.name,
        "dimensions": {
            "width": width,
            "height": height
        },
        "analysis_settings": {
            "tile_size": tile_size,
            "blur_sigma": blur_sigma,
            "flat_threshold": flat_threshold
        },
        "metrics": {
            "global_flat_region_noise_std": round(
                global_noise_std, 4
            ),
            "global_mean_absolute_residual": round(
                global_mean_absolute_residual, 4
            ),
            "median_tile_noise_std": round(
                median_tile_noise, 4
            ),
            "tile_noise_q1": round(noise_q1, 4),
            "tile_noise_q3": round(noise_q3, 4),
            "tile_noise_iqr": round(noise_iqr, 4),
            "tile_noise_coefficient_of_variation": (
                round(noise_cv, 4)
                if noise_cv is not None
                else None
            ),
            "average_flat_pixel_coverage": round(
                float(np.mean(tile_flat_coverage)), 4
            ),
            "tiles_analyzed": len(tile_noise_values)
        },
        "interpretation": (
            "These measurements describe local high-frequency "
            "variation. Differences can result from editing, "
            "compression, resizing, image content or other "
            "processing. They are not proof of manipulation."
        )
    }
