from pathlib import Path

from app.services.forensic_service import create_ela_image
from app.services.metadata_service import analyze_image_metadata
from app.services.noise_service import analyze_noise_consistency


def analyze_single_screenshot(image_path, output_dir):
    """
    Analyse one screenshot without requiring an original reference image.

    Reports metadata, ELA and noise indicators.
    Does not claim that the image is authentic or definitely manipulated.
    """

    image_path = Path(image_path)
    output_dir = Path(output_dir)

    if not image_path.is_file():
        raise FileNotFoundError(f"Screenshot not found: {image_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Metadata analysis
    metadata = analyze_image_metadata(image_path)

    # 2. Error Level Analysis
    ela = create_ela_image(
        image_path,
        output_dir / f"{image_path.stem}_ela.png"
    )

    # 3. Noise consistency analysis
    noise = None
    noise_error = None

    try:
        noise = analyze_noise_consistency(image_path)
    except Exception as error:
        noise_error = str(error)

    # 4. Interpret available evidence
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
            "No software information was found in image metadata."
        )

    if noise_error:
        indicators.append(
            f"Noise analysis could not be completed: {noise_error}"
        )

    if detected_editors:
        assessment = "POTENTIALLY_ALTERED"
    else:
        assessment = "NO_CLEAR_EDITING_INDICATORS"

    if not indicators:
        indicators.append(
            "No known editing-software metadata was detected."
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
            "has_icc_profile": metadata.get("has_icc_profile")
        },

        "ela_analysis": {
            "mean_difference": ela["mean_difference"],
            "max_difference": ela["max_difference"],
            "output_image": Path(
                ela["output_image"]
            ).name
        },

        "noise_analysis": (
            noise["metrics"] if noise else None
        ),

        "limitations": (
            "ELA and noise measurements are descriptive indicators. "
            "They can also change because of compression, resizing "
            "and normal image processing. No known editor metadata "
            "does not prove that an image is genuine."
        )
    }