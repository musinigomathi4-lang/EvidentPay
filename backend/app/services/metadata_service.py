
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import TAGS


EDITOR_KEYWORDS = (
    "photoshop",
    "photopea",
    "gimp",
    "canva",
    "snapseed",
    "picsart",
    "lightroom",
    "pixelmator",
    "affinity",
)


def _safe_value(value):
    """Convert metadata values into JSON-friendly values."""
    if isinstance(value, bytes):
        return f"<binary data: {len(value)} bytes>"

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, tuple):
        return [_safe_value(item) for item in value]

    try:
        return str(value)
    except Exception:
        return "<unreadable>"


def analyze_image_metadata(image_path):
    """
    Inspect available image metadata.

    Metadata findings are informational signals only.
    They do not establish whether an image is authentic.
    """
    image_path = Path(image_path)

    if not image_path.is_file():
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    file_size = image_path.stat().st_size

    try:
        with Image.open(image_path) as image:
            image_format = image.format
            width, height = image.size
            mode = image.mode

            image_info = {
                key: _safe_value(value)
                for key, value in image.info.items()
                if key not in ("exif", "icc_profile")
            }

            has_icc_profile = bool(
                image.info.get("icc_profile")
            )

            exif = image.getexif()

            exif_data = {}

            for tag_id, value in exif.items():
                tag_name = TAGS.get(
                    tag_id,
                    str(tag_id)
                )

                exif_data[tag_name] = _safe_value(value)

            software = (
                exif_data.get("Software")
                or image_info.get("Software")
            )

            software_text = str(software or "").lower()

            detected_editors = [
                keyword
                for keyword in EDITOR_KEYWORDS
                if keyword in software_text
            ]

            observations = []

            if not exif_data and not image_info:
                observations.append(
                    "No readable EXIF or general metadata found."
                )

            if software:
                observations.append(
                    f"Software metadata found: {software}"
                )
            else:
                observations.append(
                    "No software/editor information found."
                )

            if detected_editors:
                observations.append(
                    "Known editing software name appears in metadata."
                )

            if has_icc_profile:
                observations.append(
                    "Embedded ICC colour profile is present."
                )
            else:
                observations.append(
                    "No embedded ICC colour profile found."
                )

            return {
                "filename": image_path.name,
                "file_size_bytes": file_size,
                "format": image_format,
                "dimensions": {
                    "width": width,
                    "height": height
                },
                "colour_mode": mode,
                "has_icc_profile": has_icc_profile,
                "exif": exif_data,
                "other_metadata": image_info,
                "software": software,
                "detected_editor_keywords": detected_editors,
                "observations": observations,
                "interpretation": (
                    "Metadata provides contextual clues only. "
                    "Missing or present metadata cannot independently "
                    "prove image authenticity or manipulation."
                )
            }

    except (UnidentifiedImageError, OSError) as error:
        raise ValueError(
            f"Could not inspect image: {error}"
        ) from error
