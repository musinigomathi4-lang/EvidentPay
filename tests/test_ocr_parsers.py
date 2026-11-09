"""Focused parser tests for unseen UPI receipt text layouts."""
from backend.app.services.ocr_service import (
    _extract_payment_app,
    _extract_sender_name,
    _extract_utr,
    _amount_from_text,
)
from backend.app.utils.validators import parse_transaction_datetime, is_valid_utr


def test_phonepe_utr_label():
    text = "PhonePe Transaction ID\nT2610031802417474396167\nUTR: 656508530566"
    assert _extract_utr(text) == "656508530566"
    assert is_valid_utr(_extract_utr(text))


def test_upi_transaction_id_label():
    assert _extract_utr("UPI transaction ID\n123456789012") == "123456789012"


def test_phonepe_sender_label():
    assert _extract_sender_name("Received from\nRiya Sharma\n+91 9876543210") == "Riya Sharma"


def test_masked_sender_is_not_guessed_as_name():
    assert _extract_sender_name("Received from\nXXXXXXXX8540\n+91 XXXXX8540") is None


def test_paytm_receipt_not_recipient_upi_provider():
    text = "Payment Successful\nSent using Paytm UPI\nPaid to shop@okaxis on Google Pay"
    assert _extract_payment_app(text) == "Paytm"


def test_phonepe_receipt_detection():
    assert _extract_payment_app("Transaction Successful\nPhonePe Transaction ID\nUTR: 123456789012") == "PhonePe"


def test_time_first_date_format():
    parsed = parse_transaction_datetime("06:02 PM on 03 Oct 2026")
    assert parsed.strftime("%Y-%m-%d %H:%M") == "2026-10-03 18:02"


def test_gpay_date_format_remains_supported():
    parsed = parse_transaction_datetime("22 Sept 2026, 2:11pm")
    assert parsed.strftime("%Y-%m-%d %H:%M") == "2026-09-22 14:11"


def test_numeric_indian_date_format():
    parsed = parse_transaction_datetime("03/10/2026 18:02")
    assert parsed.strftime("%Y-%m-%d %H:%M") == "2026-10-03 18:02"


def test_currency_line_amount_fallback():
    amount, display = _amount_from_text("Payment Successful\nAmount Paid ₹1,25,000")
    assert amount == 125000
    assert display == "1,25,000"


def test_ambiguous_amounts_are_not_guessed():
    amount, display = _amount_from_text("Paid ₹500\nRefund ₹100")
    assert amount is None
    assert display is None
