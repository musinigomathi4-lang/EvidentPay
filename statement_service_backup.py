"""Flexible CSV/PDF bank statement normalization."""

import csv
from decimal import Decimal

import pdfplumber

from ..utils.helpers import (
    parse_date,
    parse_amount,
    extract_utr,
)


def _find(header, *needles, exclude=()):
    """
    Find a column whose header contains one of the requested terms.
    """

    for h in header:
        low = str(h or "").lower().replace("_", " ")

        if (
            any(n in low for n in needles)
            and not any(x in low for x in exclude)
        ):
            return h

    return None


def _find_header_row(table):
    """
    Find the actual transaction header row.

    Bank PDFs often contain:
        bank name
        account details
        statement period
        blank rows
        actual table header
    """

    for index, row in enumerate(table):

        values = [
            str(value or "").strip()
            for value in row
        ]

        joined = " ".join(values).lower()

        header_signals = sum(
            signal in joined
            for signal in (
                "date",
                "description",
                "narration",
                "particulars",
                "utr",
                "reference",
                "credit",
                "debit",
                "amount",
            )
        )

        if header_signals >= 2:
            return index

    return None


def _normalize_table(table, starting_row=1):
    """
    Normalize one independently extracted table.

    Processing each PDF table separately is important because
    pdfplumber may return a separate table for every page.
    """

    if not table:
        return []

<<<<<<< HEAD
    header_index = _find_header_row(table)
=======
    header = [str(value or "").strip() for value in rows[0]]
    c_date = (_find(header, "txn date", "transaction date", "value date", "posting date")
              or _find(header, "date"))
    c_utr = _find(header, "utr", "upi ref", "upi transaction", "transaction id", "txn id", "reference", "ref no", "ref.", "ref")
    c_desc = _find(header, "description", "narration", "particulars", "remarks", "details")
    c_credit = _find(header, "credit", "deposit", "cr amount", "received")
    c_debit = _find(header, "debit", "withdrawal", "dr amount", "paid")
    c_amount = _find(header, "amount", exclude=("credit", "debit"))
    c_type = _find(header, "type", "dr/cr", "cr/dr")
>>>>>>> 32d0f17ba771021b201aa7c909e282366f9b892c

    if header_index is None:
        return []

    header = [
        str(value or "").strip()
        for value in table[header_index]
    ]

    c_date = (
        _find(
            header,
            "txn date",
            "transaction date",
            "value date",
            "posting date",
        )
        or _find(header, "date")
    )

    c_utr = _find(
        header,
        "utr",
        "upi ref",
        "reference",
        "ref no",
        "ref.",
        "ref",
        "rrn",
        "transaction id",
    )

    c_desc = _find(
        header,
        "description",
        "narration",
        "particulars",
        "remarks",
        "details",
    )

    c_credit = _find(
        header,
        "credit",
        "deposit",
        "cr amount",
        "received",
        "credit amount",
    )

    c_debit = _find(
        header,
        "debit",
        "withdrawal",
        "dr amount",
        "paid",
        "debit amount",
    )

    c_amount = _find(
        header,
        "amount",
        exclude=("credit", "debit"),
    )

    c_type = _find(
        header,
        "type",
        "dr/cr",
        "cr/dr",
        "transaction type",
    )

    if not any(
        (
            c_date,
            c_utr,
            c_desc,
            c_credit,
            c_debit,
            c_amount,
        )
    ):
        return []

    indexes = {
        name: index
        for index, name in enumerate(header)
        if name
    }

    def cell(row, column):
        if column is None:
            return None

        index = indexes.get(column)

        if index is None:
            return None

        if index >= len(row):
            return None

        return row[index]

    transactions = []

    for local_row_number, row in enumerate(
        table[header_index + 1:],
        start=1,
    ):

        if not row:
            continue

        values = [
            str(value or "").strip()
            for value in row
        ]

        if not any(values):
            continue

        # Ignore repeated headers.
        joined = " ".join(values).lower()

        if (
            "transaction date" in joined
            or "txn date" in joined
        ) and (
            "description" in joined
            or "narration" in joined
        ):
            continue

        date_value = cell(row, c_date)
        description = str(
            cell(row, c_desc) or ""
        ).strip()

        credit = (
            parse_amount(cell(row, c_credit))
            if c_credit
            else None
        )

        debit = (
            parse_amount(cell(row, c_debit))
            if c_debit
            else None
        )

        # Some statements use one Amount column + CR/DR type.
        if (
            credit is None
            and debit is None
            and c_amount
        ):
            amount = parse_amount(
                cell(row, c_amount)
            )

            transaction_type = str(
                cell(row, c_type) or ""
            ).strip().lower()

            if amount is not None:

                if transaction_type.startswith(
                    ("cr", "credit")
                ):
                    credit = amount

                elif transaction_type.startswith(
                    ("dr", "debit")
                ):
                    debit = amount

        date = parse_date(date_value)

        utr = extract_utr(
            cell(row, c_utr) if c_utr else None,
            description,
        )

        # Ignore completely empty/non-transaction rows.
        if (
            date is None
            and utr is None
            and credit is None
            and debit is None
            and not description
        ):
            continue

        transactions.append(
            {
                "row": starting_row + local_row_number,
                "date": date,
                "utr": utr,
                "credit": credit or Decimal("0"),
                "debit": debit or Decimal("0"),
                "description": description,
            }
        )

    return transactions


def _normalize_rows(rows):
    """
    Normalize a CSV or already-flattened table list.
    """

    if not rows:
        return []

    return _normalize_table(rows)


def load_statement_csv(path):
    """
    Load a CSV bank statement.
    """

    with open(
        path,
        newline="",
        encoding="utf-8-sig",
    ) as file:

        rows = list(csv.reader(file))

    transactions = _normalize_rows(rows)

    if not transactions:
        raise ValueError(
            "No readable transaction table was found in the CSV."
        )

    return transactions


def load_statement_pdf(path):
    """
    Extract and normalize all transaction tables from every PDF page.

    Each table is normalized independently so repeated headers and
    page-level table boundaries do not destroy later transactions.
    """

    transactions = []

    with pdfplumber.open(path) as pdf:

        for page_number, page in enumerate(
            pdf.pages,
            start=1,
        ):

            tables = page.extract_tables() or []

            for table_number, table in enumerate(
                tables,
                start=1,
            ):

                cleaned = [
                    [
                        str(value or "")
                        .replace("\\n", " ")
                        .replace("\n", " ")
                        .strip()
                        for value in row
                    ]
                    for row in table
                    if row
                ]

                page_transactions = _normalize_table(
                    cleaned,
                    starting_row=len(transactions),
                )

                transactions.extend(
                    page_transactions
                )

    if not transactions:
        raise ValueError(
            "No readable transaction table was found. "
            "This PDF may be scanned/image-only, password-protected, "
            "or formatted in a way that requires a bank-specific parser. "
            "Try exporting it as CSV or provide a text-based PDF statement."
        )

    return transactions


def statement_period(txns):
    """
    Calculate the actual period represented by successfully
    parsed transactions.

    There is NO hard-coded month/year.
    """

    days = [
        transaction["date"].date()
        for transaction in txns
        if transaction["date"]
    ]

    if not days:
        return None, None

    return min(days), max(days)