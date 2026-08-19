import io
import re
from typing import Optional
import pdfplumber
from ..models.transaction import TransactionType
from .institution_profiles import PROFILES as _PROFILES

_INSTITUTION_KEYWORDS: dict[str, list[str]] = {
    # First Tech must come before Chase/Amex: First Tech checking statements
    # contain "JPMorgan Chase" and "AMEX EPAYMENT" in transaction descriptions,
    # which would falsely trigger those institutions if checked first.
    "First Tech": ["first technology federal", "first tech federal", "firsttech.com", "firsttechfed.com", "firsttechfed"],
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
_AMOUNT_RE = re.compile(r"(\(?[\-\+]?\$?[\d,]+\.\d{2}\)?)")


def _amount_to_float(raw: str) -> float:
    """Parse a matched _AMOUNT_RE token, treating parens as negative — the
    convention statements use to print a negative running balance (e.g. an
    overdrawn account shows "(589.73)")."""
    s = raw.strip().replace("$", "").replace(",", "")
    if s.startswith("(") and s.endswith(")"):
        return -float(s[1:-1])
    return float(s)

# Lines that are statement metadata/summaries, not individual transactions.
# These often contain a date and dollar amount and would otherwise be parsed
# as transactions by the text-line fallback.
_SUMMARY_LINE_RE = re.compile(
    r"new charges|previous balance|minimum (payment|due)|payment due|late fee|"
    r"credit limit|available credit|closing date|total (credit|debit|amount|charges|payments)|"
    r"account (balance|summary)|statement (balance|total)|interest charged|"
    r"opening balance|starting balance|past due|amount due|balance due|days in billing",
    re.IGNORECASE,
)


# Tolerate punctuation/words between "payment" and the acknowledgment word so
# lines like "AUTOMATIC PAYMENT - THANK YOU" still match (the " - " separator
# previously defeated a strict `payment\s+thank`).
_PAYMENT_ACK_RE = re.compile(
    r"payment\b[\s\-]+(thank\s+you|received|processed|applied|credit)",
    re.IGNORECASE,
)

# Section headers that mark the end of the transaction list. Checks-paid
# tables and daily-balance grids both contain dates and dollar amounts that
# the line fallback would otherwise misread as individual transactions, so
# once one of these is seen the rest of the document is not scanned.
_SECTION_END_RE = re.compile(
    r"^(checks?\s+paid|daily\s+balance\s+summary|"
    r"overdraft(\s+and\s+returned\s+item)?\s+fee\s+summary|"
    r"messages?\s+and\s+notices|in\s+case\s+of\s+errors)",
    re.IGNORECASE,
)

# The account's opening/closing balance line (e.g. "Beginning balance ...
# 3,182.64"). Not a transaction, but its amount seeds the running-balance
# sign heuristic in _parse_text_lines for the first real transaction line.
_BALANCE_SEED_RE = re.compile(r"beginning\s+balance|ending\s+balance", re.IGNORECASE)

_PAGE_FOOTER_RE = re.compile(r"^\d+\s+of\s+\d+$")


def _looks_like_continuation(line: str) -> bool:
    """A wrapped second line of a transaction description (e.g. the merchant
    name printed below the date/type/amount row): no date, no amount, not a
    page footer or section boundary, and in the same all-caps style banks
    print transaction text in."""
    line = line.strip()
    if not line or _DATE_RE.search(line) or _AMOUNT_RE.search(line):
        return False
    if _SECTION_END_RE.search(line) or _SUMMARY_LINE_RE.search(line) or _PAGE_FOOTER_RE.match(line):
        return False
    letters = [c for c in line if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def _needs_pdf_sign_inversion(institution: Optional[str], full_text: str) -> bool:
    """Return True when the PDF uses positive=charge convention.

    Two signals trigger inversion:
    1. The institution profile already declares invert_sign (e.g. Amex CSV).
    2. Content-based: a payment-acknowledgment line carries a negative amount,
       which means charges are positive in this PDF (Chase credit card, etc.).
    """
    if institution:
        for profile in _PROFILES:
            if profile.name == institution and profile.invert_sign:
                return True

    for line in full_text.splitlines():
        line = line.strip()
        if not _PAYMENT_ACK_RE.search(line):
            continue
        amounts = _AMOUNT_RE.findall(line)
        if not amounts:
            continue
        try:
            if _amount_to_float(amounts[-1]) < 0:
                return True
        except ValueError:
            pass

    return False


def parse_pdf(content: bytes) -> dict:
    transactions: list[dict] = []
    ambiguous: list[dict] = []
    institution: Optional[str] = None

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        # Detect institution from first-page text only to avoid false matches
        # from institution names that appear in transaction descriptions
        # (e.g. "AMEX EPAYMENT" or "JPMorgan Chase" in First Tech transactions).
        first_page_text = (pdf.pages[0].extract_text() or "") if pdf.pages else ""
        institution = _detect_institution(first_page_text)
        invert_sign = _needs_pdf_sign_inversion(institution, full_text)

        for page in pdf.pages:
            for table in page.extract_tables() or []:
                result = _parse_table(table, invert_sign=invert_sign)
                transactions.extend(result["transactions"])
                ambiguous.extend(result["ambiguous"])

        # Fallback to line-by-line if tables yielded nothing
        if not transactions:
            result = _parse_text_lines(full_text, invert_sign=invert_sign)
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


def _parse_table(table: list, invert_sign: bool = False) -> dict:
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

            amount, txn_type = _extract_table_amount(row, amount_idx, debit_idx, credit_idx, invert_sign)
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


def _extract_table_amount(row, amount_idx, debit_idx, credit_idx, invert_sign: bool = False):
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
            if invert_sign:
                v = -v
            return abs(v), TransactionType.debit if v < 0 else TransactionType.credit

    if debit_idx is not None or credit_idx is not None:
        debit = clean(row[debit_idx]) if debit_idx is not None else None
        credit = clean(row[credit_idx]) if credit_idx is not None else None
        # Separate debit/credit columns already encode direction — invert_sign
        # does not apply (column names define the sign convention explicitly).
        if credit and credit > 0:
            return credit, TransactionType.credit
        if debit and debit > 0:
            return debit, TransactionType.debit

    return None, None


def _parse_text_lines(text: str, invert_sign: bool = False) -> dict:
    transactions: list[dict] = []
    ambiguous: list[dict] = []
    # Running balance carried across lines, used to infer debit vs. credit
    # when a statement never prints an explicit +/- sign (see below).
    prev_balance: Optional[float] = None

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue

        # Once a checks-paid/daily-balance/legal section starts, nothing after
        # it is a transaction — stop scanning entirely rather than misreading
        # those tables' dates and dollar amounts as more transactions.
        if _SECTION_END_RE.search(line):
            break

        # Not a transaction, but its amount seeds the running-balance sign
        # heuristic below for the first real transaction line.
        if _BALANCE_SEED_RE.search(line):
            seed_amounts = _AMOUNT_RE.findall(line)
            if seed_amounts:
                try:
                    prev_balance = _amount_to_float(seed_amounts[-1])
                except ValueError:
                    pass
            continue

        # Skip statement summary/metadata lines — they contain dates and dollar
        # amounts but are not individual transactions.
        if _SUMMARY_LINE_RE.search(line) or "%" in line:
            continue

        date_match = _DATE_RE.search(line)
        amount_matches = _AMOUNT_RE.findall(line)

        if not date_match or not amount_matches:
            continue

        try:
            parsed_date = _parse_date(date_match.group(1))
            if not parsed_date:
                continue

            # Amex foreign-currency rows print "<foreign> $<usd>": the USD charge
            # is $-prefixed and is the real transaction amount, not a running
            # balance — there's no trailing balance column on that line at all.
            # Otherwise, bank statements end each line with a running balance
            # after the transaction amount, so when two or more amounts are
            # present the last is the balance — use the second-to-last as the
            # transaction amount and keep the last as that line's balance.
            line_balance_str: Optional[str] = None
            if len(amount_matches) >= 2:
                if "$" in amount_matches[-1] and "$" not in amount_matches[-2]:
                    txn_amount_str = amount_matches[-1]
                else:
                    txn_amount_str = amount_matches[-2]
                    line_balance_str = amount_matches[-1]
            else:
                txn_amount_str = amount_matches[-1]
            value = _amount_to_float(txn_amount_str)
            has_explicit_sign = txn_amount_str.strip().startswith(("-", "+", "("))

            if invert_sign:
                value = -value

            line_balance: Optional[float] = None
            if line_balance_str is not None:
                try:
                    line_balance = _amount_to_float(line_balance_str)
                except ValueError:
                    line_balance = None

            # Direction: trust an explicit sign (or a profile's invert_sign)
            # first. Otherwise, when this line carries a running balance and we
            # know the prior one, a balance that dropped means a debit and a
            # balance that rose means a credit — needed for statements (like
            # this one) that print every amount as a plain positive number and
            # convey direction only via column position, which plain-text
            # extraction loses. Falls back to the old (credit-by-default)
            # behavior when neither signal is available.
            if has_explicit_sign or invert_sign:
                is_debit = value < 0
            elif line_balance is not None and prev_balance is not None and abs(line_balance - prev_balance) >= 0.005:
                is_debit = line_balance < prev_balance
            else:
                is_debit = value < 0

            if line_balance is not None:
                prev_balance = line_balance

            desc_start = date_match.end()
            txn_amount_pos = line.rfind(txn_amount_str)
            description = line[desc_start:txn_amount_pos].strip() if txn_amount_pos > desc_start else line.strip()
            if not description:
                description = line
            # A second "Date Posted" column leaves its own date token stuck to
            # the front of the description slice above — drop it.
            description = re.sub(r"^\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?\s+", "", description)

            # Bank statements often wrap the merchant name onto the line below
            # the date/amount row — pull those continuation lines back in so
            # the merchant isn't lost.
            extra_lines = []
            while i < len(lines) and _looks_like_continuation(lines[i]):
                extra_lines.append(lines[i].strip())
                i += 1
            if extra_lines:
                description = f"{description} {' '.join(extra_lines)}".strip()

            transactions.append({
                "date": parsed_date,
                "description": description,
                "amount": abs(value),
                "transaction_type": TransactionType.debit if is_debit else TransactionType.credit,
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
