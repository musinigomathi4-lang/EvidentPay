from pathlib import Path
import re

from app.services.forensic_service import (
    analyze_screenshot_pair,
    create_ela_image,
)
from app.services.metadata_service import analyze_image_metadata
from app.services.noise_service import analyze_noise_consistency
from app.services.ocr_service import extract_payment


def _normalise(value, field):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    if field == "amount":
        digits = re.sub(r"[^0-9]", "", value)
        return digits or None

    if field == "utr":
        return re.sub(r"[^A-Z0-9]", "", value.upper()) or None

    if field == "date":
        return value[:10]

    if field == "sender_name":
        return re.sub(r"[^A-Z0-9]", "", value.upper()) or None

    return value


def _compare_ocr_fields(original_path, modified_path):
    original = extract_payment(str(original_path))
    modified = extract_payment(str(modified_path))

    fields = {
        "amount": "Amount",
        "utr": "UTR",
        "transaction_date": "Transaction date",
        "sender_name": "Sender name",
    }

    comparisons = {}
    mismatches = []

    for field, label in fields.items():
        original_value = original.get(field)
        modified_value = modified.get(field)

        original_normalised = _normalise(original_value, field)
        modified_normalised = _normalise(modified_value, field)

        if original_normalised and modified_normalised:
            matches = original_normalised == modified_normalised

            comparisons[field] = {
                "label": label,
                "original_value": original_value,
                "modified_value": modified_value,
                "matches": matches,
                "status": "MATCH" if matches else "DIFFERENT",
            }

            if not matches:
                mismatches.append(
                    f"{label} differs: original '{original_value}', "
                    f"uploaded '{modified_value}'"
                )
        else:
            comparisons[field] = {
                "label": label,
                "original_value": original_value,
                "modified_value": modified_value,
                "matches": None,
                "status": "NOT_COMPARABLE",
            }

    return {
        "comparisons": comparisons,
        "mismatches": mismatches,
        "original_ocr_confidence": original.get("confidence"),
        "modified_ocr_confidence": modified.get("confidence"),
    }


def analyze_paired_screenshot(original_path, modified_path, output_dir):
    """
    Compare an uploaded screenshot with its known genuine reference.

    This is reference-based forensic analysis. It does not verify
    whether a payment reached a bank account.
    """
    original_path = Path(original_path)
    modified_path = Path(modified_path)
    output_dir = Path(output_dir)

    if not original_path.is_file():
        raise FileNotFoundError(
            f"Genuine reference not found: {original_path}"
        )

    if not modified_path.is_file():
        raise FileNotFoundError(
            f"Uploaded screenshot not found: {modified_path}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    indicators = []

    pair_analysis = analyze_screenshot_pair(
        original_path,
        modified_path,
        output_dir,
    )

    ocr_comparison = _compare_ocr_fields(
        original_path,
        modified_path,
    )

    indicators.extend(ocr_comparison["mismatches"])

    original_noise = None
    modified_noise = None
    noise_comparison = None

    try:
        original_noise = analyze_noise_consistency(original_path)
        modified_noise = analyze_noise_consistency(modified_path)

        original_metrics = original_noise["metrics"]
        modified_metrics = modified_noise["metrics"]

        noise_comparison = {
            key: {
                "original": original_metrics.get(key),
                "modified": modified_metrics.get(key),
            }
            for key in (
                "global_flat_region_noise_std",
                "median_tile_noise_std",
                "tile_noise_iqr",
                "tile_noise_coefficient_of_variation",
            )
        }

    except Exception as error:
        indicators.append(
            f"Noise comparison could not be completed: {error}"
        )

    localized = pair_analysis["localized_analysis"]
    edge = pair_analysis["edge_analysis"]

    phash_distance = pair_analysis["phash_distance"]
    changed_pixel_percent = localized["changed_pixel_percent"]
    edge_difference_percent = edge["edge_difference_percent"]

    # OCR field differences are direct content-level evidence.
    if ocr_comparison["mismatches"]:
        assessment = "POTENTIALLY_ALTERED"

    # Structural differences are review signals, not proof.
    elif (
        phash_distance >= 6
        or changed_pixel_percent >= 0.5
        or edge_difference_percent >= 0.5
    ):
        assessment = "REVIEW_RECOMMENDED"
        indicators.append(
            "The genuine and uploaded images contain structural "
            "differences that need manual review."
        )

    else:
        assessment = "NO_CLEAR_EDITING_INDICATORS"
        indicators.append(
            "No major differences were identified by the configured "
            "reference-based checks. This does not prove authenticity."
        )

    metadata = analyze_image_metadata(modified_path)

    if metadata.get("detected_editor_keywords"):
        indicators.append(
            "Editing software information was found in image metadata: "
            + ", ".join(metadata["detected_editor_keywords"])
        )

    return {
        "filename": modified_path.name,
        "assessment": assessment,
        "indicators": indicators,
        "reference_comparison": {
            "original_filename": original_path.name,
            "modified_filename": modified_path.name,
            "phash_distance": phash_distance,
            "changed_pixel_percent": changed_pixel_percent,
            "edge_difference_percent": edge_difference_percent,
            "regions_detected": localized["regions_detected"],
            "regions": localized["regions"],
            "annotated_image": Path(
                localized["annotated_image"]
            ).name,
            "ssim_heatmap": Path(
                localized["heatmap_image"]
            ).name,
            "edge_difference_image": Path(
                edge["output_image"]
            ).name,
        },
        "ocr_comparison": ocr_comparison,
        "noise_comparison": noise_comparison,
        "ela_comparison": {
            "original_mean_difference": pair_analysis[
                "original_ela"
            ]["mean_difference"],
            "modified_mean_difference": pair_analysis[
                "modified_ela"
            ]["mean_difference"],
            "original_ela_image": Path(
                pair_analysis["original_ela"]["output_image"]
            ).name,
            "modified_ela_image": Path(
                pair_analysis["modified_ela"]["output_image"]
            ).name,
        },
        "metadata_analysis": {
            "format": metadata.get("format"),
            "dimensions": metadata.get("dimensions"),
            "software": metadata.get("software"),
            "detected_editors": metadata.get(
                "detected_editor_keywords", []
            ),
            "has_icc_profile": metadata.get("has_icc_profile"),
        },
        "limitations": (
            "This result compares the uploaded image with a known "
            "reference. OCR differences can be affected by extraction "
            "errors. Compression, resizing and image content can affect "
            "forensic measurements. Findings require human review and "
            "do not establish payment receipt."
        ),
    }


def analyze_single_screenshot(image_path, output_dir):
    """
    Analyse one screenshot when no genuine reference is available.
    Missing metadata is not treated as evidence of authenticity.
    """
    image_path = Path(image_path)
    output_dir = Path(output_dir)

    if not image_path.is_file():
        raise FileNotFoundError(f"Screenshot not found: {image_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = analyze_image_metadata(image_path)

    ela = create_ela_image(
        image_path,
        output_dir / f"{image_path.stem}_ela.png",
    )

    noise = None
    noise_error = None

    try:
        noise = analyze_noise_consistency(image_path)
    except Exception as error:
        noise_error = str(error)

    detected_editors = metadata.get(
        "detected_editor_keywords", []
    )

    indicators = []

    if detected_editors:
        indicators.append(
            "Known image-editing software was identified in metadata: "
            + ", ".join(detected_editors)
        )

    if not metadata.get("software"):
        indicators.append(
            "No software information was found in image metadata. "
            "WhatsApp may remove metadata during sharing."
        )

    if noise_error:
        indicators.append(
            f"Noise analysis could not be completed: {noise_error}"
        )

    if not indicators:
        indicators.append(
            "No specific single-image editing indicators were identified."
        )

    # A single image without a genuine reference cannot be declared clean.
    assessment = (
        "POTENTIALLY_ALTERED"
        if detected_editors
        else "REVIEW_RECOMMENDED"
    )

    return {
        "filename": image_path.name,
        "assessment": assessment,
        "indicators": indicators,
        "metadata_analysis": {
            "format": metadata.get("format"),
            "dimensions": metadata.get("dimensions"),
            "software": metadata.get("software"),
            "detected_editors": detected_editors,
            "has_icc_profile": metadata.get("has_icc_profile"),
        },
        "ela_analysis": {
            "mean_difference": ela["mean_difference"],
            "max_difference": ela["max_difference"],
            "output_image": Path(ela["output_image"]).name,
        },
        "noise_analysis": noise["metrics"] if noise else None,
        "limitations": (
            "Single-image ELA, metadata and noise analysis cannot "
            "reliably establish whether an image was manipulated. "
            "A genuine reference image is required for direct comparison."
        ),
    }