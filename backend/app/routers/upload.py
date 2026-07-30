import hashlib
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile, Depends
from sqlmodel import Session

from ..database import get_session, get_engine
from ..dependencies import get_current_user
from ..models.import_job import ImportJob, ImportStatus
from ..models.transaction import Transaction, TransactionType
from ..models.user import User
from ..parsers.csv_parser import parse_csv
from ..parsers.pdf_parser import parse_pdf
from ..rate_limit import limiter
from ..services.duplicate_detector import (
    is_duplicate,
    file_already_imported,
    existing_job_for_file,
)
from ..services.encryption import encrypt
from ..services.expense_categorizer import categorize_expense
from ..services.income_classifier import classify_income, credit_expense_category
from ..services.transfer_detector import detect_and_mark
from ..config import get_settings

router = APIRouter(prefix="/api", tags=["upload"])
logger = logging.getLogger("personalcfo.upload")


def _is_pdf(content: bytes) -> bool:
    return content[:4] == b"%PDF"


def _date_range(transactions: list[dict]) -> dict:
    if not transactions:
        return {}
    dates = [t["date"] for t in transactions]
    return {"from": str(min(dates)), "to": str(max(dates))}


def _run_ai_categorization(user_id: int, job_id: str) -> None:
    """Background worker: AI-categorize a job's fallback rows in a fresh session.

    Runs after the upload response is returned so income review (F2) is available
    immediately; categories are ready by the time the user finishes review."""
    from ..services.ai_categorizer import categorize_job
    with Session(get_engine()) as session:
        try:
            categorize_job(session, user_id, job_id)
        except Exception:
            logger.exception(f"ai categorization failed job_id={job_id}")


@router.post("/upload")
@limiter.limit("10/minute")
async def upload_statements(
    request: Request,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    job_id = str(uuid.uuid4())
    logger.info(f"upload started user_id={current_user.id} file_count={len(files)}")
    job = ImportJob(id=job_id, user_id=current_user.id, file_count=len(files), status=ImportStatus.processing)
    session.add(job)
    session.flush()

    file_results = []
    total_saved = 0
    duplicate_job_id: str | None = None  # existing import for skipped re-uploads

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

        # Skip a file whose exact content was already imported. is_duplicate()
        # only flags identical rows from a *different* hash, so without this a
        # same-file re-upload would duplicate the whole statement.
        if file_already_imported(session, current_user.id, file_hash):
            existing = existing_job_for_file(session, current_user.id, file_hash)
            file_results.append({
                "file": upload.filename,
                "error": "Already imported — skipped to avoid duplicates",
                "already_imported": True,
                "existing_job_id": existing,
            })
            if existing:
                duplicate_job_id = existing
            continue

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
                current_user.id,
                txn_data["date"],
                txn_data["amount"],
                txn_data["transaction_type"],
                file_hash,
            )

            if txn_data["transaction_type"] == TransactionType.debit:
                exp_primary, exp_sub, exp_source = categorize_expense(txn_data["description"])
                # Rule hits are high-confidence; fallbacks await the AI pass.
                exp_conf, exp_label = (1.0, "high") if exp_source == "rule" else (None, "low")
            else:
                # Card-side incoming payments (PAYMENT THANK YOU, AUTOPAY RECEIVED)
                # are tagged as a credit-card payment so they're explicitly a
                # non-spending transfer, not an uncategorized credit (AMI-14).
                cc = credit_expense_category(txn_data["description"])
                if cc:
                    exp_primary, exp_sub, exp_source = cc, cc, "rule"
                    exp_conf, exp_label = 1.0, "high"
                else:
                    exp_primary, exp_sub, exp_source = None, None, None
                    exp_conf, exp_label = None, None

            txn = Transaction(
                user_id=current_user.id,
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
                expense_category=exp_primary,
                expense_subcategory=exp_sub,
                category_source=exp_source,
                category_confidence=exp_conf,
                confidence_label=exp_label,
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

    # Cross-account transfer pairing runs once over the whole job, after every
    # file is persisted, so transfers between two imported accounts are matched.
    transfer_summary = detect_and_mark(session, job_id)

    job.total_transactions = total_saved
    job.status = ImportStatus.pending_income_review
    job.completed_at = datetime.utcnow()
    session.add(job)
    session.commit()

    logger.info(
        f"upload completed job_id={job_id} status={job.status} txn_count={total_saved}"
    )

    # AI categorization of the long tail runs after the response is sent.
    background_tasks.add_task(_run_ai_categorization, current_user.id, job_id)

    return {
        "import_job_id": job_id,
        "file_results": file_results,
        "total_transactions": total_saved,
        "transfers_paired": transfer_summary["paired"],
        "transfers_unconfirmed": transfer_summary["unconfirmed"],
        "status": job.status,
        # When everything was a duplicate, point the UI to the existing import.
        "existing_job_id": duplicate_job_id,
    }


def _looks_like_csv(content: bytes) -> bool:
    try:
        sample = content[:1024].decode("utf-8", errors="replace")
        return "," in sample or "\t" in sample
    except Exception:
        return False
