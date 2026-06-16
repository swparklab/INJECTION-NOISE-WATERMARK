"""Provenance, evidence and audit endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_watermark_service
from app.core.tracking_engine import TrackingEngine, TraceResult
from app.core.watermark_engine import WatermarkService
from app.provenance.audit import AuditService
from app.provenance.c2pa import C2PAManifest, C2PAService
from app.reports.evidence import EvidenceService
from app.schemas.api import AuditVerifyResponse, EvidenceResponse, ProvenanceVerifyResponse

router = APIRouter(tags=["provenance"])


@router.post("/provenance/verify", response_model=ProvenanceVerifyResponse)
async def verify_provenance(manifest: dict) -> ProvenanceVerifyResponse:
    """Verify a C2PA content-credential manifest's signature."""
    try:
        m = C2PAManifest(**manifest)
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid manifest: {exc}") from exc
    c2pa = C2PAService()
    valid = c2pa.verify_manifest(m)
    return ProvenanceVerifyResponse(
        valid=valid,
        asset_id=m.asset_id,
        watermark_model=m.watermark_model,
        detail={"delivery_id": m.delivery_id, "recipient": m.recipient_id},
    )


@router.post("/evidence/generate", response_model=EvidenceResponse)
async def generate_evidence(
    trace_id: str,
    report_type: str = "forensic",
    session: Session = Depends(db_session),
) -> EvidenceResponse:
    """Generate a signed evidence report from a stored trace id."""
    from app.db.models import WatermarkTrace

    row = session.get(WatermarkTrace, trace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="trace not found")

    trace = TraceResult(
        found=bool(row.recipient_id),
        asset_id=row.asset_id,
        delivery_id=row.delivery_id,
        recipient_id=row.recipient_id,
        watermark_model=row.watermark_model,
        confidence=row.confidence,
        signature_valid=row.signature_valid,
        trace_path=row.trace_path,
        detail={**row.detail, "trace_id": row.id},
    )
    ev = EvidenceService(session)
    report = ev.generate(trace, report_type)
    session.commit()
    return EvidenceResponse(
        report_type=report.report_type,
        generated_at=report.generated_at,
        signature=report.signature,
        public_key=report.public_key,
        audit_chain_valid=report.audit_chain_valid,
        statements=report.statements,
        trace=report.trace,
    )


@router.get("/audit/verify", response_model=AuditVerifyResponse)
async def verify_audit(session: Session = Depends(db_session)) -> AuditVerifyResponse:
    """Verify the integrity of the append-only audit chain."""
    valid, n = AuditService(session).verify_chain()
    return AuditVerifyResponse(valid=valid, entries=n)


@router.get("/audit/logs")
async def list_audit_logs(
    limit: int = 100, session: Session = Depends(db_session)
) -> list[dict]:
    """List recent audit log entries."""
    from app.db.models import AuditLog

    rows = (
        session.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    )
    return [
        {
            "id": r.id,
            "actor": r.actor,
            "action": r.action,
            "resource_id": r.resource_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "detail": r.detail,
        }
        for r in rows
    ]
