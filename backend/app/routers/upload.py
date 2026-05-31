import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
from sqlmodel import Session

from ..database import get_session
from ..models.import_job import ImportJob, ImportStatus
from ..models.transaction import Transaction, TransactionType
from ..parsers.csv_parser import parse_csv
from ..parsers.pdf_parser import parse_pdf
from ..services.duplicate_detector import is_duplicate
from ..services.encryption import encrypt
from ..services.expense_categorizer import categorize_expense
from ..services.income_classifier import classify_income
from ..config import get_settings

router = APIRouter(prefix="/api", tags=["upload"])


def _is_pdf(content: bytes) -> bool:
    return content[:4] == b"%PDF"


def _date_range(transactions: list[dict]) -> dict:
    if not transactions:
        return {}
    dates = [t["date"] for t in transactions]
    return {"from": str(min(dates)), "to": str(max(dates))}


@router.post("/upload")
async def upload_statements(
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
):
    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    job_id = str(uuid.uuid4())
    job = ImportJob(id=job_id, file_count=len(files), status=ImportStatus.processing)
    session.add(job)
    session.flush()

    file_results = []
    total_saved = 0

    for upload in files:
        content = await upload.read()

        if len(content) > max_bytes:
            file_results.append({
                "file": upload.filename,
                "error": f"File exceeds {settings.max_upload_size_mb}MB limit",
            })
            continue

        # Validate file type by content signature, not MIME header
        if not (_is_pdf(content) or _looks_like_csv(content)):
            file_results.append({
                "file": upload.filename,
                "error": "File must be a CSV or PDF",
            })
            continue

        file_hash = hashlib.sha256(content).hexdigest()

        try:
            parsed = parse_pdf(content) if _is_pdf(content) else parse_csv(content)
        except Exception as e:
            file_results.append({"file": upload.filename, "error": f"Parse error: {e}"})
            continue

        saved_txns: list[Transaction] = []

        for txn_data in parsed["transactions"]:
            is_candidate, income_cat = classify_income(
                txn_data["description"],
                txn_data["amount"],
                txn_data["transaction_type"],
            )
            is_dup = is_duplicate(
                session,
                txn_data["date"],
                txn_data["amount"],
                txn_data["transaction_type"],
                file_hash,
            )

            exp_cat = (
                categorize_expense(txn_data["description"])
                if txn_data["transaction_type"] == TransactionType.debit
                else None
            )

            txn = Transaction(
                import_job_id=job_id,
                date=txn_data["date"],
                description=encrypt(txn_data["description"]),
                amount=txn_data["amount"],
                transaction_type=txn_data["transaction_type"],
                currency=txn_data.get("currency", "USD"),
                institution=parsed.get("institution"),
                source_file_hash=file_hash,
                is_income_candidate=is_candidate,
                income_category=income_cat.value if income_cat else None,
                expense_category=exp_cat,
                is_duplicate=is_dup,
            )
            session.add(txn)
            saved_txns.append(txn)

        session.flush()  # assign IDs; makes subsequent duplicate checks within same job work

        credits = [t for t in saved_txns if t.transaction_type == TransactionType.credit]
        debits = [t for t in saved_txns if t.transaction_type == TransactionType.debit]

        file_results.append({
            "file": upload.filename,
            "institution": parsed.get("institution"),
            "institution_confidence_pct": round((parsed.get("confidence") or 0) * 100),
            "transactions_found": len(parsed["transactions"]),
            "transactions_saved": len(saved_txns),
            "date_range": _date_range(parsed["transactions"]),
            "total_credits": round(sum(t.amount for t in credits), 2),
            "total_debits": round(sum(t.amount for t in debits), 2),
            "income_candidates_count": sum(1 for t in saved_txns if t.is_income_candidate),
            "duplicate_count": sum(1 for t in saved_txns if t.is_duplicate),
            "ambiguous_count": len(parsed["ambiguous"]),
            "warnings": [a.get("detail", "") for a in parsed["ambiguous"][:5]],
        })
        total_saved += len(saved_txns)

    job.total_transactions = total_saved
    job.status = ImportStatus.pending_income_review
    job.completed_at = datetime.utcnow()
    session.add(job)
    session.commit()

    return {
        "import_job_id": job_id,
        "file_results": file_results,
        "total_transactions": total_saved,
        "status": job.status,
    }


def _looks_like_csv(content: bytes) -> bool:
    try:
        sample = content[:1024].decode("utf-8", errors="replace")
        return "," in sample or "\t" in sample
    except Exception:
        return False
