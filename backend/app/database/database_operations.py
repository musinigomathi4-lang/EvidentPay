
import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from .connection import SessionLocal
from .models import (
    Event,
    PaymentClaim,
    BankTransaction,
    ReconciliationResult,
)


# --------------------------------------------------
# Helper functions
# --------------------------------------------------

def _to_datetime(value):
    """Convert supported date values into Python datetime objects."""

    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value

    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return datetime.combine(value, datetime.min.time())

    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _to_decimal(value):
    """Convert a numeric value into Decimal safely."""

    if value is None or value == "":
        return None

    return Decimal(str(value))


def _json_text(value):
    """Convert Python data into JSON text for SQLite storage."""

    return json.dumps(value, default=str)


# --------------------------------------------------
# 1. EVENT OPERATIONS
# --------------------------------------------------

def create_event(event_name, event_price, expected_participant_count=None):
    """Create and save a new event."""

    db = SessionLocal()

    try:
        event = Event(
            event_name=event_name,
            event_price=_to_decimal(event_price),
            expected_participant_count=expected_participant_count,
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        return event

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def get_event(event_id):
    """Retrieve an event using its ID."""

    db = SessionLocal()

    try:
        return db.query(Event).filter(
            Event.event_id == event_id
        ).first()

    finally:
        db.close()


# --------------------------------------------------
# 2. PAYMENT CLAIM OPERATIONS
# --------------------------------------------------

def save_payment_claim(event_id, screenshot_filename, screenshot_path, ocr_data):
    """
    Save one screenshot and its OCR-extracted information.

    ocr_data is the dictionary returned by extract_payment().
    """

    db = SessionLocal()

    try:
        claim = PaymentClaim(
            event_id=event_id,

            screenshot_filename=screenshot_filename,
            screenshot_path=str(screenshot_path),

            amount=_to_decimal(ocr_data.get("amount")),
            utr=ocr_data.get("utr"),

            transaction_date=_to_datetime(
                ocr_data.get("transaction_date") or ocr_data.get("date")
            ),

            transaction_time=ocr_data.get("transaction_time"),

            sender_name=ocr_data.get("sender_name"),
            contact_name=ocr_data.get("contact_name"),
            payment_app=ocr_data.get("payment_app"),
            payment_status=ocr_data.get("status"),

            raw_text=ocr_data.get("raw_text"),
            confidence=_to_decimal(ocr_data.get("confidence")),

            flags_json=_json_text(ocr_data.get("flags", [])),
            needs_review=int(bool(ocr_data.get("needs_review", False))),
        )

        db.add(claim)
        db.commit()
        db.refresh(claim)

        return claim

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def get_payment_claims(event_id):
    """Retrieve all screenshot claims belonging to an event."""

    db = SessionLocal()

    try:
        return db.query(PaymentClaim).filter(
            PaymentClaim.event_id == event_id
        ).order_by(PaymentClaim.claim_id).all()

    finally:
        db.close()


def get_payments_for_matching(event_id):
    """
    Convert saved payment claims into the input format
    expected by matching_service.match_payments().
    """

    db = SessionLocal()

    try:
        claims = db.query(PaymentClaim).filter(
            PaymentClaim.event_id == event_id
        ).order_by(PaymentClaim.claim_id).all()

        payments = []

        for claim in claims:
            payments.append({
                # Database claim ID becomes the matching payment ID.
                "id": claim.claim_id,

                "amount": claim.amount,
                "utr": claim.utr,
                "date": claim.transaction_date,

                "flags": json.loads(claim.flags_json or "[]"),
                "needs_review": bool(claim.needs_review),
            })

        return payments

    finally:
        db.close()


# --------------------------------------------------
# 3. BANK TRANSACTION OPERATIONS
# --------------------------------------------------

def save_bank_transactions(event_id, transactions, source_file=None):
    """
    Save parsed bank statement transactions.

    transactions is the list returned by load_statement_csv().
    """

    db = SessionLocal()

    try:
        saved_transactions = []

        for txn in transactions:
            bank_txn = BankTransaction(
                event_id=event_id,

                source_file=source_file,
                statement_row=txn.get("row"),

                transaction_date=_to_datetime(txn.get("date")),
                utr=txn.get("utr"),

                credit=_to_decimal(txn.get("credit")) or Decimal("0"),
                debit=_to_decimal(txn.get("debit")) or Decimal("0"),

                description=txn.get("description"),
            )

            db.add(bank_txn)
            saved_transactions.append(bank_txn)

        db.commit()

        for txn in saved_transactions:
            db.refresh(txn)

        return saved_transactions

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def get_bank_transactions(event_id):
    """Retrieve all bank transactions belonging to an event."""

    db = SessionLocal()

    try:
        return db.query(BankTransaction).filter(
            BankTransaction.event_id == event_id
        ).order_by(BankTransaction.statement_row).all()

    finally:
        db.close()


def get_transactions_for_matching(event_id):
    """
    Convert saved bank records into the input format
    expected by matching_service.match_payments().
    """

    db = SessionLocal()

    try:
        transactions = db.query(BankTransaction).filter(
            BankTransaction.event_id == event_id
        ).order_by(BankTransaction.statement_row).all()

        return [
            {
                "row": txn.statement_row,
                "date": txn.transaction_date,
                "utr": txn.utr,
                "credit": txn.credit,
                "debit": txn.debit,
                "description": txn.description or "",
            }
            for txn in transactions
        ]

    finally:
        db.close()


# --------------------------------------------------
# 4. RECONCILIATION OPERATIONS
# --------------------------------------------------

def save_reconciliation_results(event_id, results):
    """
    Save results returned by matching_service.match_payments().

    The matcher's payment_id is the database claim_id.
    Bank transaction rows are linked using statement_row.
    """

    db = SessionLocal()

    try:
        claims = db.query(PaymentClaim).filter(
            PaymentClaim.event_id == event_id
        ).all()

        bank_transactions = db.query(BankTransaction).filter(
            BankTransaction.event_id == event_id
        ).all()

        claim_ids = {claim.claim_id for claim in claims}

        bank_row_map = {
            txn.statement_row: txn.bank_transaction_id
            for txn in bank_transactions
        }

        saved_results = []

        for result in results:
            claim_id = result.get("payment_id")

            if claim_id not in claim_ids:
                raise ValueError(
                    f"Payment claim {claim_id} does not belong to event {event_id}"
                )

            bank_data = result.get("bank_transaction")
            bank_transaction_id = None

            if bank_data:
                bank_row = bank_data.get("row")
                bank_transaction_id = bank_row_map.get(bank_row)

                if bank_transaction_id is None:
                    raise ValueError(
                        f"Bank statement row {bank_row} was not found "
                        f"for event {event_id}"
                    )

            saved_result = ReconciliationResult(
                claim_id=claim_id,
                bank_transaction_id=bank_transaction_id,

                status=result.get("status"),
                reasons_json=_json_text(result.get("reasons", [])),
                checks_json=_json_text(result.get("checks", {})),
            )

            db.add(saved_result)
            saved_results.append(saved_result)

        db.commit()

        for result in saved_results:
            db.refresh(result)

        return saved_results

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def get_reconciliation_results(event_id):
    """Retrieve reconciliation results for an event."""

    db = SessionLocal()

    try:
        return (
            db.query(ReconciliationResult)
            .join(PaymentClaim)
            .filter(PaymentClaim.event_id == event_id)
            .order_by(ReconciliationResult.result_id)
            .all()
        )

    finally:
        db.close()
