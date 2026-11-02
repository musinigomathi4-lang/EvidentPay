"""Duplicate payment claims: the same bank transaction (same UTR) claimed by several screenshots."""


def find_duplicate_claims(payments):
    """payments: list of dicts with 'id' and 'utr', in claim order (earliest first).

    The first screenshot carrying a UTR is the valid claim; later ones with the same UTR are
    duplicates of it. Payments without a UTR are skipped (OCR could not read them: that is a
    review case, not evidence of a duplicate).

    Returns {duplicate_payment_id: first_payment_id}.
    """
    first_by_utr = {}
    duplicates = {}
    for p in payments:
        utr = p.get("utr")
        if not utr:
            continue
        if utr not in first_by_utr:
            first_by_utr[utr] = p["id"]
        else:
            duplicates[p["id"]] = first_by_utr[utr]
    return duplicates