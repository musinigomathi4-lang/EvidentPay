
import json

from app.services.metadata_service import (
    analyze_image_metadata
)

IMAGE_PATH = r"..\uploads\screenshots\real_ss\1.jpeg"

result = analyze_image_metadata(IMAGE_PATH)

print(json.dumps(result, indent=4))
