import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import get_current_user
from ..models.import_job import ImportJob
from ..models.insight import Insight
from ..models.user import User
from ..services.insight_engine import generate_insights, dashboard_insights, latest_ledger_insights

router = APIRouter(prefix="/api", tags=["insights"])

_SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


def _serialize(ins: Insight) -> dict:
    return {
        "id": ins.id,
        "import_job_id": ins.import_job_id,
        "insight_type": ins.insight_type,
        "title": ins.title,
        "explanation": ins.explanation,
        "severity": ins.severity,
        "confidence": ins.confidence,
        "confidence_label": ins.confidence_label,
        "time_period_start": str(ins.time_period_start) if ins.time_period_start else None,
        "time_period_end": str(ins.time_period_end) if ins.time_period_end else None,
        "supporting_transaction_ids": json.loads(ins.supporting_transaction_ids),
        "suggested_next_step": ins.suggested_next_step,
        "is_dismissed": ins.is_dismissed,
        "created_at": ins.created_at.isoformat(),
        "metadata": json.loads(ins.meta_json),
    }


@router.post("/import/{job_id}/generate-insights")
def trigger_insights(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    job = session.get(ImportJob, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Import job not found")
    new = generate_insights(session, current_user.id, job_id)
    return {
        "job_id": job_id,
        "insights_generated": len(new),
        "insight_ids": [i.id for i in new],
    }


@router.get("/import/{job_id}/dashboard-insights")
def get_dashboard_insights(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Top-3 proactive insights for the per-import summary page (AMI-48)."""
    job = session.get(ImportJob, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Import job not found")
    return {"insights": dashboard_insights(session, current_user.id, job_id)}


@router.get("/summary/insights")
def get_summary_insights(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Top-3 proactive insights for the whole-ledger 'View import' page (AMI-48)."""
    return {"insights": latest_ledger_insights(session, current_user.id)}


@router.get("/insights")
def get_insight_feed(
    severity: Optional[str] = None,
    type: Optional[str] = None,
    include_dismissed: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    query = select(Insight).where(Insight.user_id == current_user.id)
    if not include_dismissed:
        query = query.where(Insight.is_dismissed == False)  # noqa: E712
    if severity:
        query = query.where(Insight.severity == severity)
    if type:
        query = query.where(Insight.insight_type == type)

    rows = session.exec(query).all()
    rows_sorted = sorted(rows, key=lambda i: (_SEV_ORDER.get(i.severity, 3), -i.confidence, -i.created_at.timestamp()))
    serialized = [_serialize(i) for i in rows_sorted]

    counts = {"high": 0, "medium": 0, "low": 0}
    for s in serialized:
        if not s["is_dismissed"] and s["severity"] in counts:
            counts[s["severity"]] += 1

    return {
        "insights": serialized,
        "total": len(serialized),
        "high_severity_count": counts["high"],
        "medium_severity_count": counts["medium"],
        "low_severity_count": counts["low"],
    }


@router.patch("/insights/{insight_id}/dismiss")
def dismiss_insight(
    insight_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    ins = session.get(Insight, insight_id)
    if not ins or ins.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Insight not found")
    ins.is_dismissed = True
    session.add(ins)
    session.commit()
    return {"id": insight_id, "is_dismissed": True}
