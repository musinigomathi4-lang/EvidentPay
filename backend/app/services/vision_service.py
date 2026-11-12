
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
from google import genai
from google.genai import types


BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

MODEL_NAME = "gemini-2.5-flash"


def _empty_result(error=None):
    return {
        "configured": bool(os.getenv("GEMINI_API_KEY")),
        "available": False,
        "model": MODEL_NAME,
        "assessment": "REVIEW_RECOMMENDED",
        "confidence": None,
        "findings": [],
        "suspicious_regions": [],
        "limitations": [
            "Visual AI analysis was unavailable. This does not mean the screenshot is genuine."
        ],
        "error": error
    }


def _parse_json(text):
    text = (text or "").strip()

    # Remove optional Markdown JSON fences.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    return json.loads(text)


def _normalise_regions(regions):
    normalised = []

    if not isinstance(regions, list):
        return normalised

    for region in regions[:10]:
        if not isinstance(region, dict):
            continue

        try:
            x = float(region["x"])
            y = float(region["y"])
            width = float(region["width"])
            height = float(region["height"])
        except (KeyError, TypeError, ValueError):
            continue

        # Reject invalid or zero-sized boxes.
        if width <= 0 or height <= 0:
            continue

        x = max(0.0, min(1.0, x))
        y = max(0.0, min(1.0, y))
        width = max(0.0, min(width, 1.0 - x))
        height = max(0.0, min(height, 1.0 - y))

        if width == 0 or height == 0:
            continue

        normalised.append({
            "x": round(x, 4),
            "y": round(y, 4),
            "width": round(width, 4),
            "height": round(height, 4),
            "reason": str(region.get("reason", "Region suggested for manual review"))[:300]
        })

    return normalised


def analyze_image_with_vision(image_path):
    """
    Ask Gemini to review visual consistency in one image.

    This is supporting visual analysis only. It does not verify a payment
    or prove that an image has or has not been manipulated.
    """

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return _empty_result("GEMINI_API_KEY is not configured in backend/.env")

    image_path = Path(image_path)

    if not image_path.is_file():
        return _empty_result("Screenshot file was not found.")

    prompt = """
You are assisting with a cautious visual-forensics review of a payment screenshot.

Inspect ONLY the visible pixels and visual layout of this image.
Do NOT decide whether a payment actually happened.
Do NOT verify UTRs, bank credits, balances, or payment status.
Do NOT assume that a screenshot is fake merely because it is compressed,
cropped, resized, shared through WhatsApp, or missing metadata.

Look for concrete visual inconsistencies such as:
- text with noticeably different sharpness, compression, or rendering from nearby text
- inconsistent font size, weight, alignment, spacing, or baseline
- unusual edges, patches, halos, or visible compositing around text or numbers
- UI elements that appear visually inconsistent with the rest of the screenshot

Be conservative. A normal screenshot can contain compression artefacts.
If there is no clear visual evidence, say so.

Return ONLY valid JSON using this exact structure:
{
  "assessment": "POTENTIALLY_ALTERED" | "REVIEW_RECOMMENDED" | "NO_CLEAR_VISUAL_INDICATORS",
  "confidence": "LOW" | "MEDIUM" | "HIGH",
  "findings": ["short concrete observation"],
  "suspicious_regions": [
    {
      "x": 0.10,
      "y": 0.20,
      "width": 0.25,
      "height": 0.08,
      "reason": "What looks visually inconsistent"
    }
  ],
  "limitations": ["short limitation"]
}

Region coordinates MUST be normalized from 0 to 1 relative to the full image:
x and y are the top-left corner; width and height are the box dimensions.
Only include a region when you can point to a specific visible area.
Do not invent coordinates. Return an empty array if no specific region can be identified.
"""

    try:
        client = genai.Client(
           api_key=api_key,
           http_options={"api_version": "v1beta"}
)

        with Image.open(image_path) as image:
            image = image.convert("RGB")

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[prompt, image],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )

        data = _parse_json(response.text)

        allowed_assessments = {
            "POTENTIALLY_ALTERED",
            "REVIEW_RECOMMENDED",
            "NO_CLEAR_VISUAL_INDICATORS"
        }

        assessment = str(data.get("assessment", "REVIEW_RECOMMENDED")).upper()

        if assessment not in allowed_assessments:
            assessment = "REVIEW_RECOMMENDED"

        findings = data.get("findings", [])
        limitations = data.get("limitations", [])

        return {
            "configured": True,
            "available": True,
            "model": MODEL_NAME,
            "assessment": assessment,
            "confidence": str(data.get("confidence", "LOW")).upper(),
            "findings": [
                str(item)[:500]
                for item in findings[:10]
            ] if isinstance(findings, list) else [],
            "suspicious_regions": _normalise_regions(
                data.get("suspicious_regions", [])
            ),
            "limitations": [
                str(item)[:500]
                for item in limitations[:10]
            ] if isinstance(limitations, list) else [],
            "error": None
        }

    except Exception as error:
        return _empty_result(
            f"Gemini visual analysis failed: {str(error)[:500]}"
        )
