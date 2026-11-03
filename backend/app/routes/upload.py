
import json
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.database.database_operations import (
    create_event,
    get_event,
    get_payment_claims,
    save_payment_claim,
)
from app.services.ocr_service import extract_payment


router = APIRouter(prefix="/api/events", tags=["Events"])

BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "uploads" / "screenshots"

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024


class EventCreateRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=150)
    event_price: float = Field(gt=0)
    expected_participant_count: int = Field(gt=0)


@router.post("")
def create_new_event(payload: EventCreateRequest):
    if not payload.event_name.strip():
        raise HTTPException(
            status_code=400,
            detail="Event name cannot be empty"
        )

    event = create_event(
        event_name=payload.event_name.strip(),
        event_price=payload.event_price,
        expected_participant_count=payload.expected_participant_count
    )

    return {
        "event_id": event.event_id,
        "event_name": event.event_name,
        "event_price": str(event.event_price),
        "expected_participant_count": event.expected_participant_count
    }


@router.post("/{event_id}/screenshots")
def upload_screenshots(
    event_id: int,
    files: list[UploadFile] = File(...)
):
    event = get_event(event_id)

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    for file in files:
        saved_path = None

        try:
            extension = Path(file.filename or "").suffix.lower()

            if extension not in ALLOWED_EXTENSIONS:
                results.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": "Unsupported image format"
                })
                continue

            unique_filename = f"{uuid4().hex}{extension}"
            saved_path = UPLOAD_DIR / unique_filename

            with open(saved_path, "wb") as destination:
                shutil.copyfileobj(file.file, destination)

            if saved_path.stat().st_size == 0:
                raise ValueError("Empty image file")

            if saved_path.stat().st_size > MAX_FILE_SIZE:
                raise ValueError("Image exceeds the 10 MB limit")

            ocr_data = extract_payment(str(saved_path))

            claim = save_payment_claim(
                event_id=event_id,
                screenshot_filename=file.filename,
                screenshot_path=str(saved_path),
                ocr_data=ocr_data
            )

            results.append({
                "filename": file.filename,
                "status": "success",
                "claim_id": claim.claim_id,
                "ocr_data": ocr_data
            })

        except Exception as error:
            if saved_path and saved_path.exists():
                saved_path.unlink()

            results.append({
                "filename": file.filename,
                "status": "failed",
                "error": str(error)
            })

        finally:
            file.file.close()

    successful = sum(
        1 for result in results
        if result["status"] == "success"
    )

    return {
        "event_id": event_id,
        "total_files": len(files),
        "successful": successful,
        "failed": len(files) - successful,
        "results": results
    }


@router.get("/{event_id}/claims")
def retrieve_payment_claims(event_id: int):
    event = get_event(event_id)

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    claims = get_payment_claims(event_id)

    return {
        "event_id": event_id,
        "total_claims": len(claims),
        "claims": [
            {
                "claim_id": claim.claim_id,
                "screenshot_filename": claim.screenshot_filename,
                "amount": (
                    str(claim.amount)
                    if claim.amount is not None else None
                ),
                "utr": claim.utr,
                "transaction_date": (
                    claim.transaction_date.isoformat()
                    if claim.transaction_date else None
                ),
                "transaction_time": claim.transaction_time,
                "payment_app": claim.payment_app,
                "payment_status": claim.payment_status,
                "confidence": (
                    str(claim.confidence)
                    if claim.confidence is not None else None
                ),
                "flags": (
                    json.loads(claim.flags_json)
                    if claim.flags_json else []
                ),
                "needs_review": bool(claim.needs_review)
            }
            for claim in claims
        ]
    }
