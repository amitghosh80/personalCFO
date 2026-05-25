import io
import pandas as pd
from datetime import date as DateType
from typing import Optional
from .institution_profiles import detect_institution, InstitutionProfile
from ..models.transaction import TransactionType


def parse_csv(content: bytes) -> dict:
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        return {"institution": None, "confidence": 0.0, "transactions": [], "ambiguous": [
            {"reason": "csv_read_error", "detail": str(e)}
        ]}

    df.columns = [c.strip() for c in df.columns]
    profile, confidence = detect_institution(df.columns.tolist())

    if profile is None or confidence < 0.7:
        return {
            "institution": None,
            "confidence": confidence,
            "transactions": [],
            "ambiguous": [{
                "reason": "unknown_institution",
                "detail": f"Unrecognized column layout: {df.columns.tolist()}. "
                          "Supported banks: Chase, Bank of America, Citi, Capital One, American Express, Wells Fargo.",
            }],
        }

    transactions = []
    ambiguous = []

    for idx, row in df.iterrows():
        result = _parse_row(row, profile, row_num=int(idx) + 2)
        if result is None:
            continue
        if "error" in result:
            ambiguous.append(result)
        else:
            transactions.append(result)

    return {
        "institution": profile.name,
        "confidence": confidence,
        "transactions": transactions,
        "ambiguous": ambiguous,
    }


def _parse_row(row, profile: InstitutionProfile, row_num: int) -> Optional[dict]:
    date_str = str(row.get(profile.date_col, "")).strip()
    description = str(row.get(profile.description_col, "")).strip()

    if not description or description.lower() in ("nan", ""):
        return None
    if not date_str or date_str.lower() in ("nan", ""):
        return None

    try:
        parsed_date = pd.to_datetime(date_str, format=profile.date_format).date()
    except Exception:
        try:
            parsed_date = pd.to_datetime(date_str).date()
        except Exception:
            return {"reason": "ambiguous_date", "detail": f"Row {row_num}: cannot parse date '{date_str}'", "row": row_num}

    try:
        amount, txn_type = _extract_amount(row, profile)
    except Exception as e:
        return {"reason": "amount_parse_error", "detail": f"Row {row_num}: {e}", "row": row_num}

    if amount == 0.0:
        return None

    return {
        "date": parsed_date,
        "description": description,
        "amount": amount,
        "transaction_type": txn_type,
        "currency": "USD",
    }


def _extract_amount(row, profile: InstitutionProfile) -> tuple[float, TransactionType]:
    if profile.amount_col:
        raw = str(row.get(profile.amount_col, "0")).replace(",", "").replace("$", "").strip()
        if not raw or raw.lower() == "nan":
            raise ValueError("empty amount field")
        value = float(raw)
        if profile.invert_sign:
            value = -value
        return abs(value), TransactionType.debit if value < 0 else TransactionType.credit

    # Separate debit / credit columns
    def _clean(val) -> float:
        s = str(val).replace(",", "").replace("$", "").strip()
        return float(s) if s and s.lower() not in ("nan", "") else 0.0

    debit = _clean(row.get(profile.debit_col, 0))
    credit = _clean(row.get(profile.credit_col, 0))

    if credit > 0:
        return credit, TransactionType.credit
    if debit > 0:
        return debit, TransactionType.debit
    raise ValueError("both debit and credit are zero or missing")
