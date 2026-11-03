
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Numeric,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from .connection import Base


class Event(Base):
    __tablename__ = "events"

    event_id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String(150), nullable=False)
    event_price = Column(Numeric(12, 2), nullable=False)
    expected_participant_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    payment_claims = relationship(
        "PaymentClaim", back_populates="event",
        cascade="all, delete-orphan"
    )

    bank_transactions = relationship(
        "BankTransaction", back_populates="event",
        cascade="all, delete-orphan"
    )


class PaymentClaim(Base):
    __tablename__ = "payment_claims"

    claim_id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.event_id"), nullable=False)

    screenshot_filename = Column(String(255), nullable=False)
    screenshot_path = Column(String(500), nullable=False)

    amount = Column(Numeric(12, 2))
    utr = Column(String(30), index=True)
    transaction_date = Column(DateTime)
    transaction_time = Column(String(30))

    sender_name = Column(String(150))
    contact_name = Column(String(150))
    payment_app = Column(String(50))
    payment_status = Column(String(50))

    raw_text = Column(Text)
    confidence = Column(Numeric(5, 2))
    flags_json = Column(Text)
    needs_review = Column(Integer, default=0)

    uploaded_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="payment_claims")

    reconciliation_results = relationship(
        "ReconciliationResult", back_populates="claim",
        cascade="all, delete-orphan"
    )


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    bank_transaction_id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.event_id"), nullable=False)

    source_file = Column(String(255))
    statement_row = Column(Integer)
    external_transaction_id = Column(String(100))

    transaction_date = Column(DateTime)
    utr = Column(String(30), index=True)

    credit = Column(Numeric(12, 2), default=0)
    debit = Column(Numeric(12, 2), default=0)

    description = Column(Text)

    event = relationship("Event", back_populates="bank_transactions")

    reconciliation_results = relationship(
        "ReconciliationResult", back_populates="bank_transaction"
    )


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"

    result_id = Column(Integer, primary_key=True, index=True)

    claim_id = Column(
        Integer, ForeignKey("payment_claims.claim_id"), nullable=False
    )

    bank_transaction_id = Column(
        Integer, ForeignKey("bank_transactions.bank_transaction_id"),
        nullable=True
    )

    status = Column(String(50), nullable=False)
    reasons_json = Column(Text)
    checks_json = Column(Text)

    reconciled_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship(
        "PaymentClaim", back_populates="reconciliation_results"
    )

    bank_transaction = relationship(
        "BankTransaction", back_populates="reconciliation_results"
    )
