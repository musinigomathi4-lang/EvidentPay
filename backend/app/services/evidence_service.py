from pathlib import Path
from decimal import Decimal, InvalidOperation
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
        # Parse INR values numerically so display formatting does not create
        # false mismatches (for example, "1,000.00" and "1000").
        amount_text = re.sub(r"(?i)\bINR\b", "", value)
        amount_text = amount_text.replace("₹", "").replace(",", "")
        amount_text = re.sub(r"\s+", "", amount_text)
        if not re.fullmatch(r"[+-]?\d+(?:\.\d{1,2})?", amount_text):
            return None
        try:
            amount = Decimal(amount_text)
        except InvalidOperation:
            return None
        return format(amount.normalize(), "f")

    if field == "utr":
        return re.sub(r"[^A-Z0-9]", "", value.upper()) or None

    if field in {"date", "transaction_date"}:
        return value[:10]

    if field == "sender_name":
        return re.sub(r"[^A-Z0-9]", "", value.upper()) or None

    return value


def _compare_ocr_fields(original_path, modified_path, original_ocr=None, modified_ocr=None):
    original = original_ocr or extract_payment(str(original_path))
    modified = modified_ocr or extract_payment(str(modified_path))

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


def analyze_paired_screenshot(original_path, modified_path, output_dir, original_ocr=None, modified_ocr=None):
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
        original_ocr=original_ocr,
        modified_ocr=modified_ocr,
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
            "Known image-editing software was identified in metadata. "
            "This is a review signal, not proof that the payment screenshot "
            "was manipulated: " + ", ".join(detected_editors)
        )

    if noise_error:
        indicators.append(
            f"Noise analysis could not be completed: {noise_error}"
        )

    if not indicators:
        indicators.append(
            "No credible genuine reference was available. ELA and noise "
            "measurements are descriptive only and cannot determine whether "
            "this screenshot was manipulated."
        )

    # Without a genuine reference, single-image checks cannot establish
    # manipulation. Keep the result explicitly inconclusive.
    assessment = "INCONCLUSIVE"

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

_REFERENCE_ANALYSIS_CACHE = {}


def find_genuine_reference(uploaded_path, reference_dir, uploaded_ocr=None,
                           max_phash_distance=24, candidate_limit=12):
    """
    Find a likely genuine reference by image content, never by filename.

    pHash retrieves visually similar candidates. OCR field agreement then
    checks whether a candidate plausibly depicts the same payment. The search
    keeps a wider visual shortlist so small edits, recompression and resizing
    do not eliminate the genuine reference too early. A candidate is accepted
    only when its UTR matches or at least two extracted fields agree. This is
    reference retrieval, not proof of authenticity.
    """
    import imagehash
    from PIL import Image

    uploaded_path = Path(uploaded_path)
    reference_dir = Path(reference_dir)

    if not uploaded_path.is_file() or not reference_dir.is_dir():
        return None

    if uploaded_ocr is None:
        uploaded_ocr = extract_payment(str(uploaded_path))

    def normalise(value, field):
        if value is None:
            return None
        value = str(value).strip()
        if not value:
            return None
        if field == "amount":
            return _normalise(value, field)
        if field == "utr":
            return re.sub(r"[^A-Z0-9]", "", value.upper()) or None
        if field == "transaction_date":
            return value[:10]
        if field == "sender_name":
            return re.sub(r"[^A-Z0-9]", "", value.upper()) or None
        return value

    fields = ("utr", "amount", "transaction_date", "sender_name")

    try:
        with Image.open(uploaded_path) as image:
            uploaded_hash = imagehash.phash(image.convert("RGB"))
    except Exception:
        return None

    candidates = []
    for reference_path in reference_dir.iterdir():
        if not reference_path.is_file() or reference_path.suffix.lower() not in {
            ".png", ".jpg", ".jpeg", ".webp"
        }:
            continue
        try:
            stat = reference_path.stat()
            cache_key = str(reference_path.resolve())
            signature = (stat.st_mtime_ns, stat.st_size)
            cached = _REFERENCE_ANALYSIS_CACHE.get(cache_key)
            if cached and cached["signature"] == signature:
                reference_hash = cached["phash"]
            else:
                with Image.open(reference_path) as image:
                    reference_hash = imagehash.phash(image.convert("RGB"))
                _REFERENCE_ANALYSIS_CACHE[cache_key] = {
                    "signature": signature,
                    "phash": reference_hash,
                    "ocr": None,
                }
            distance = int(uploaded_hash - reference_hash)
            if distance <= max_phash_distance:
                candidates.append((distance, reference_path))
        except Exception:
            continue

    candidates.sort(key=lambda item: item[0])
    candidates = candidates[:candidate_limit]

    best_match = None
    for distance, reference_path in candidates:
        cache_key = str(reference_path.resolve())
        cached = _REFERENCE_ANALYSIS_CACHE[cache_key]
        if cached["ocr"] is None:
            cached["ocr"] = extract_payment(str(reference_path))
        reference_ocr = cached["ocr"]
        matching_fields = []
        for field in fields:
            uploaded_value = normalise(uploaded_ocr.get(field), field)
            reference_value = normalise(reference_ocr.get(field), field)
            if (
                uploaded_value
                and reference_value
                and uploaded_value == reference_value
            ):
                matching_fields.append(field)

        # UTR is a strong transaction-specific identifier. If OCR could not
        # read it, require agreement on at least two other extracted fields.
        credible = (
            "utr" in matching_fields
            or len(matching_fields) >= 2
        )
        if not credible:
            continue

        candidate = {
            "path": reference_path,
            "filename": reference_path.name,
            "phash_distance": distance,
            "matching_fields": matching_fields,
            "matching_field_count": len(matching_fields),
            "reference_ocr": {
                field: reference_ocr.get(field)
                for field in ("amount", "utr", "transaction_date", "sender_name")
            },
        }
        if (
            best_match is None
            or candidate["matching_field_count"] > best_match["matching_field_count"]
            or (
                candidate["matching_field_count"] == best_match["matching_field_count"]
                and distance < best_match["phash_distance"]
            )
        ):
            best_match = candidate

    if best_match is None:
        return {
            "found": False,
            "candidate_count": len(candidates),
            "reason": (
                "No visually similar reference also had enough matching "
                "payment fields to establish a credible comparison."
            ),
        }

    return {
        "found": True,
        "filename": best_match["filename"],
        "phash_distance": best_match["phash_distance"],
        "matching_fields": best_match["matching_fields"],
        "matching_field_count": best_match["matching_field_count"],
        "candidate_count": len(candidates),
        "reference_ocr": best_match["reference_ocr"],
        "path": best_match["path"],
    }
