
import json
import shutil

from pathlib import Path
from uuid import uuid4
from collections import Counter
import hashlib

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.database.database_operations import (
    create_event,
    get_event,
    get_payment_claims,
    get_bank_transactions,
    get_payments_for_matching,
    get_transactions_for_matching,
    get_reconciliation_results,
    save_payment_claim,
    save_bank_transactions,
    save_reconciliation_results,
)

from app.services.ocr_service import extract_payment
from app.services.statement_service import load_statement_csv, load_statement_pdf
from app.services.matching_service import match_payments


router = APIRouter(prefix="/api/events", tags=["Events"])

BACKEND_DIR = Path(__file__).resolve().parents[2]

SCREENSHOT_DIR = BACKEND_DIR / "uploads" / "screenshots"
STATEMENT_DIR = BACKEND_DIR / "uploads" / "statements"

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_STATEMENT_SIZE = 20 * 1024 * 1024


class EventCreateRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=150)
    event_price: float = Field(gt=0)
    expected_participant_count: int = Field(gt=0)


# --------------------------------------------------
# 1. CREATE EVENT
# --------------------------------------------------

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


# --------------------------------------------------
# 2. UPLOAD PAYMENT SCREENSHOTS
# --------------------------------------------------

@router.post("/{event_id}/screenshots")
def upload_screenshots(
    event_id: int,
    files: list[UploadFile] = File(...)
):

    event = get_event(event_id)

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    for file in files:

        saved_path = None

        try:
            extension = Path(file.filename or "").suffix.lower()

            if extension not in ALLOWED_IMAGE_EXTENSIONS:
                results.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": "Unsupported image format"
                })
                continue

            unique_filename = f"{uuid4().hex}{extension}"
            saved_path = SCREENSHOT_DIR / unique_filename

            with open(saved_path, "wb") as destination:
                shutil.copyfileobj(file.file, destination)

            if saved_path.stat().st_size == 0:
                raise ValueError("Empty image file")

            if saved_path.stat().st_size > MAX_IMAGE_SIZE:
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


# --------------------------------------------------
# 3. RETRIEVE PAYMENT CLAIMS
# --------------------------------------------------

@router.get("/{event_id}/claims")
def retrieve_payment_claims(event_id: int):

    event = get_event(event_id)

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

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
                "sender_name": claim.sender_name,
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


# --------------------------------------------------
# 4. UPLOAD BANK STATEMENT (CSV)
# --------------------------------------------------

@router.post("/{event_id}/statement")
def upload_bank_statement(
    event_id: int,
    file: UploadFile = File(...)
):

    event = get_event(event_id)

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    extension = Path(file.filename or "").suffix.lower()

    if extension not in {".csv", ".pdf"}:
        raise HTTPException(
            status_code=400,
            detail="Upload a CSV or PDF bank statement"
        )

    # Prevent duplicate imports for the same event.
    existing_transactions = get_bank_transactions(event_id)

    if existing_transactions:
        raise HTTPException(
            status_code=409,
            detail="A bank statement has already been imported for this event"
        )

    STATEMENT_DIR.mkdir(parents=True, exist_ok=True)

    saved_path = None
    database_saved = False

    try:
        unique_filename = f"{uuid4().hex}{extension}"
        saved_path = STATEMENT_DIR / unique_filename

        with open(saved_path, "wb") as destination:
            shutil.copyfileobj(file.file, destination)

        if saved_path.stat().st_size == 0:
            raise HTTPException(
                status_code=400,
                detail="The uploaded statement is empty"
            )

        if saved_path.stat().st_size > MAX_STATEMENT_SIZE:
            raise HTTPException(
                status_code=400,
                detail="Statement exceeds the 20 MB limit"
            )

        # Parse CSV using the existing statement service.
        transactions = (
            load_statement_pdf(str(saved_path))
            if extension == ".pdf"
            else load_statement_csv(str(saved_path))
        )

        if not transactions:
            raise HTTPException(
                status_code=400,
                detail="No transactions found in the statement"
            )

        usable_transactions = [
            txn for txn in transactions
            if (
                txn["date"] is not None
                or txn["utr"] is not None
                or txn["credit"] > 0
                or txn["debit"] > 0
            )
        ]

        if not usable_transactions:
            raise HTTPException(
                status_code=400,
                detail="Could not extract usable transaction data from this CSV"
            )

        # Save normalized transactions into SQLite.
        saved_transactions = save_bank_transactions(
            event_id=event_id,
            transactions=transactions,
            source_file=file.filename
        )

        database_saved = True

        credit_count = sum(
            1 for txn in transactions
            if txn["credit"] > 0
        )

        debit_count = sum(
            1 for txn in transactions
            if txn["debit"] > 0
        )

        return {
            "event_id": event_id,
            "filename": file.filename,
            "total_transactions": len(saved_transactions),
            "credit_transactions": credit_count,
            "debit_transactions": debit_count,
            "message": "Bank statement uploaded and saved successfully"
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read the bank statement: {str(error)}"
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Statement processing failed: {str(error)}"
        )

    finally:
        if (
            saved_path
            and saved_path.exists()
            and not database_saved
        ):
            saved_path.unlink()

        file.file.close()


# --------------------------------------------------
# 4B. SCREENSHOT-ONLY REVIEW (NO BANK STATEMENT)
# --------------------------------------------------

@router.post("/{event_id}/analyze-without-statement")
def analyze_without_statement(event_id: int):
    """Create an explicitly unverified review when no recipient statement is available."""
    event = get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    claims = get_payments_for_matching(event_id)
    if not claims:
        raise HTTPException(
            status_code=400,
            detail="Upload payment screenshots before starting screenshot-only review"
        )

    if get_reconciliation_results(event_id):
        raise HTTPException(
            status_code=409,
            detail="This event already has review results"
        )

    duplicate_utr_counts = Counter(
        str(claim.get("utr")).strip()
        for claim in claims
        if claim.get("utr")
    )
    results = []
    for claim in claims:
        utr = str(claim.get("utr") or "").strip()
        reasons = [
            "No recipient-side bank statement was supplied. This payment is NOT verified."
        ]
        if not claim.get("amount"):
            reasons.append("Amount could not be reliably extracted from the screenshot.")
        if not utr:
            reasons.append("UTR could not be extracted from the screenshot.")
        if utr and duplicate_utr_counts[utr] > 1:
            reasons.append("The same UTR appears in multiple uploaded claims.")

        results.append({
            "payment_id": claim["id"],
            "bank_transaction": None,
            "status": "UNVERIFIED_NO_BANK_STATEMENT",
            "reasons": reasons,
            "checks": {
                "amount_extracted": bool(claim.get("amount")),
                "utr_extracted": bool(utr),
                "duplicate_utr_in_uploads": bool(utr and duplicate_utr_counts[utr] > 1),
                "bank_credit_confirmed": False
            }
        })

    saved = save_reconciliation_results(event_id=event_id, results=results)
    return {
        "event_id": event_id,
        "total_claims": len(claims),
        "total_reconciled": len(saved),
        "verified": 0,
        "unverified": len(saved),
        "message": "Screenshot-only review completed. No payment has been bank-verified."
    }


# --------------------------------------------------
# 5. RECONCILE PAYMENTS
# --------------------------------------------------

@router.post("/{event_id}/reconcile")
def reconcile_event_payments(event_id: int):

    event = get_event(event_id)

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    payments = get_payments_for_matching(event_id)

    transactions = get_transactions_for_matching(event_id)

    if not payments:
        raise HTTPException(
            status_code=400,
            detail="No payment screenshots have been uploaded"
        )

    if not transactions:
        raise HTTPException(
            status_code=400,
            detail="No bank statement has been uploaded"
        )

    existing_results = get_reconciliation_results(event_id)

    if existing_results:
        raise HTTPException(
            status_code=409,
            detail="This event has already been reconciled"
        )

    # Existing deterministic matching logic.
    results = match_payments(
        payments=payments,
        transactions=transactions
    )

    # Persist results in SQLite.
    saved_results = save_reconciliation_results(
        event_id=event_id,
        results=results
    )

    summary = Counter(
        result["status"] for result in results
    )

    return {
        "event_id": event_id,
        "total_claims": len(payments),
        "total_bank_transactions": len(transactions),
        "total_reconciled": len(saved_results),
        "summary": dict(summary),
        "message": "Payment reconciliation completed"
    }


# --------------------------------------------------
# 6. RETRIEVE RECONCILIATION RESULTS
# --------------------------------------------------

@router.get("/{event_id}/results")
def retrieve_reconciliation_results(event_id: int):

    event = get_event(event_id)

    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    results = get_reconciliation_results(event_id)

    claims = get_payment_claims(event_id)

    bank_transactions = get_bank_transactions(event_id)

    claim_map = {
        claim.claim_id: claim
        for claim in claims
    }

    bank_map = {
        txn.bank_transaction_id: txn
        for txn in bank_transactions
    }

    return {
        "event_id": event_id,
        "total_results": len(results),
        "results": [
            {
                "result_id": result.result_id,
                "claim_id": result.claim_id,

                "screenshot_filename": (
                    claim_map[result.claim_id].screenshot_filename
                    if result.claim_id in claim_map else None
                ),

                "screenshot_amount": (
                    str(claim_map[result.claim_id].amount)
                    if (
                        result.claim_id in claim_map
                        and claim_map[result.claim_id].amount is not None
                    )
                    else None
                ),

                "screenshot_utr": (
                    claim_map[result.claim_id].utr
                    if result.claim_id in claim_map else None
                ),

                "status": result.status,

                "reasons": (
                    json.loads(result.reasons_json)
                    if result.reasons_json else []
                ),

                "checks": (
                    json.loads(result.checks_json)
                    if result.checks_json else {}
                ),

                "bank_transaction": (
                    {
                        "transaction_id": bank_map[
                            result.bank_transaction_id
                        ].bank_transaction_id,
                        "statement_row": bank_map[
                            result.bank_transaction_id
                        ].statement_row,
                        "utr": bank_map[
                            result.bank_transaction_id
                        ].utr,
                        "credit": str(
                            bank_map[
                                result.bank_transaction_id
                            ].credit
                        ),
                        "date": (
                            bank_map[
                                result.bank_transaction_id
                            ].transaction_date.isoformat()
                            if bank_map[
                                result.bank_transaction_id
                            ].transaction_date else None
                        )
                    }
                    if result.bank_transaction_id in bank_map
                    else None
                )
            }
            for result in results
        ]
    }
