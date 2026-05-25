import io
import re
from typing import Optional
import pdfplumber
from ..models.transaction import TransactionType

_INSTITUTION_KEYWORDS: dict[str, list[str]] = {
    "Chase": ["jpmorgan chase", "chase bank", "chase.com"],
    "Bank of America": ["bank of america", "bankofamerica"],
    "Wells Fargo": ["wells fargo"],
    "Citi": ["citibank", "citi bank", "citicards", "citi.com"],
    "Capital One": ["capital one"],
    "American Express": ["american express", "americanexpress", "amex"],
}

_DATE_RE = re.compile(
    r"\b(\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?|\d{4}[/\-]\d{2}[/\-]\d{2})\b"
)
_AMOUNT_RE = re.compile(r"([\-\+]?\$?[\d,]+\.\d{2})")


def parse_pdf(content: bytes) -> dict:
    transactions: list[dict] = []
    ambiguous: list[dict] = []
    institution: Optional[str] = None

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        institution = _detect_institution(full_text)

        for page in pdf.pages:
            for table in page.extract_tables() or []:
                result = _parse_table(table)
                transactions.extend(result["transactions"])
                ambiguous.extend(result["ambiguous"])

        # Fallback to line-by-line if tables yielded nothing
        if not transactions:
            result = _parse_text_lines(full_text)
            transactions.extend(result["transactions"])
            ambiguous.extend(result["ambiguous"])

    return {
        "institution": institution,
        "confidence": 0.75 if institution else 0.3,
        "transactions": transactions,
        "ambiguous": ambiguous,
    }


def _detect_institution(text: str) -> Optional[str]:
    lower = text.lower()
    for name, keywords in _INSTITUTION_KEYWORDS.items():
        if any(k in lower for k in keywords):
            return name
    return None


def _parse_table(table: list) -> dict:
    transactions: list[dict] = []
    ambiguous: list[dict] = []

    if not table or len(table) < 2:
        return {"transactions": transactions, "ambiguous": ambiguous}

    header = [str(c).strip().lower() if c else "" for c in table[0]]

    date_idx = next((i for i, h in enumerate(header) if "date" in h), None)
    desc_idx = next((i for i, h in enumerate(header) if any(k in h for k in ["desc", "memo", "narration", "detail", "payee"])), None)
    amount_idx = next((i for i, h in enumerate(header) if h == "amount"), None)
    debit_idx = next((i for i, h in enumerate(header) if "debit" in h or "withdrawal" in h), None)
    credit_idx = next((i for i, h in enumerate(header) if "credit" in h or "deposit" in h), None)

    if date_idx is None or desc_idx is None:
        ambiguous.append({"reason": "table_no_headers", "detail": f"Could not identify date/description columns in: {header}"})
        return {"transactions": transactions, "ambiguous": ambiguous}

    for row in table[1:]:
        if not row or all(not c or str(c).strip() in ("", "None") for c in row):
            continue
        try:
            date_str = str(row[date_idx]).strip() if row[date_idx] else ""
            description = str(row[desc_idx]).strip() if row[desc_idx] else ""

            if not date_str or not description or date_str.lower() == "none":
                continue

            parsed_date = _parse_date(date_str)
            if not parsed_date:
                ambiguous.append({"reason": "ambiguous_date", "detail": f"Cannot parse date '{date_str}'"})
                continue

            amount, txn_type = _extract_table_amount(row, amount_idx, debit_idx, credit_idx)
            if amount is None:
                continue

            transactions.append({
                "date": parsed_date,
                "description": description,
                "amount": amount,
                "transaction_type": txn_type,
                "currency": "USD",
            })
        except Exception as e:
            ambiguous.append({"reason": "table_row_error", "detail": str(e)})

    return {"transactions": transactions, "ambiguous": ambiguous}


def _extract_table_amount(row, amount_idx, debit_idx, credit_idx):
    def clean(val) -> Optional[float]:
        if val is None:
            return None
        s = str(val).replace(",", "").replace("$", "").replace("(", "-").replace(")", "").strip()
        if not s or s.lower() == "none":
            return None
        try:
            return float(s)
        except ValueError:
            return None

    if amount_idx is not None:
        v = clean(row[amount_idx])
        if v is not None:
            return abs(v), TransactionType.credit if v >= 0 else TransactionType.debit

    if debit_idx is not None or credit_idx is not None:
        debit = clean(row[debit_idx]) if debit_idx is not None else None
        credit = clean(row[credit_idx]) if credit_idx is not None else None
        if credit and credit > 0:
            return credit, TransactionType.credit
        if debit and debit > 0:
            return debit, TransactionType.debit

    return None, None


def _parse_text_lines(text: str) -> dict:
    transactions: list[dict] = []
    ambiguous: list[dict] = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        date_match = _DATE_RE.search(line)
        amount_matches = _AMOUNT_RE.findall(line)

        if not date_match or not amount_matches:
            continue

        try:
            parsed_date = _parse_date(date_match.group(1))
            if not parsed_date:
                continue

            # Bank statements often end each line with a running balance after the
            # transaction amount. When two or more amounts are present, the last is
            # the running balance; use the second-to-last as the transaction amount.
            txn_amount_str = amount_matches[-2] if len(amount_matches) >= 2 else amount_matches[-1]
            raw_amount = txn_amount_str.replace("$", "").replace(",", "")
            value = float(raw_amount)

            desc_start = date_match.end()
            txn_amount_pos = line.rfind(txn_amount_str)
            description = line[desc_start:txn_amount_pos].strip() if txn_amount_pos > desc_start else line.strip()
            if not description:
                description = line

            transactions.append({
                "date": parsed_date,
                "description": description,
                "amount": abs(value),
                "transaction_type": TransactionType.credit if value >= 0 else TransactionType.debit,
                "currency": "USD",
            })
        except Exception as e:
            ambiguous.append({"reason": "line_parse_error", "detail": f"Line: {line[:60]} — {e}"})

    return {"transactions": transactions, "ambiguous": ambiguous}


def _parse_date(date_str: str):
    import pandas as pd
    from datetime import date as DateClass
    try:
        dt = pd.to_datetime(date_str).date()
        # MM/DD-only strings parse with year=1; substitute current year.
        if dt.year < 2000:
            dt = dt.replace(year=DateClass.today().year)
        return dt
    except Exception:
        return None
