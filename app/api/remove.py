"""Remove endpoints: rights-holder watermark removal / forensic isolation."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_watermark_service
from app.config.settings import get_settings
from app.core.removal_engine import RemovalEngine
from app.core.watermark_engine import WatermarkService
from app.payload.service import TokenCodec
from app.provenance.audit import AuditService
from app.schemas.api import RemoveResponse
from app.utils import media

router = APIRouter(tags=["remove"])


@router.post("/remove", response_model=RemoveResponse)
async def remove_watermark(
    file: UploadFile = File(...),
    method: str = Form("frequency_suppression"),
    asset_id: str | None = Form(None),
    model: str = Form("custom-noise"),
    requested_by: str = Form(""),
    service: WatermarkService = Depends(get_watermark_service),
    session: Session = Depends(db_session),
) -> RemoveResponse:
    """Remove (or isolate) a watermark from an uploaded image.

    ``template_cancellation`` requires ``asset_id`` so the keyed pattern can be
    regenerated. All removals are audit-logged.
    """
    raw = await file.read()
    try:
        image = media.decode_image(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    settings = get_settings()
    engine = RemovalEngine()
    tc = TokenCodec()
    key = service._key_for_asset(asset_id) if asset_id else None

    try:
        result = engine.remove(image, method=method, key=key, model_id=model, wire_len=tc.wire_len())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    out_dir = Path(settings.data_dir) / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"removed-{uuid.uuid4()}.png"
    out_path.write_bytes(media.encode_image(result.image, ".png"))

    # Persist removal record + audit.
    from app.db.models import WatermarkRemoval

    row = WatermarkRemoval(
        asset_id=asset_id,
        method=method,
        watermark_detected=result.watermark_detected_before,
        removal_success=result.removal_success,
        quality_score=result.quality_score,
        requested_by=requested_by,
        detail=result.detail,
    )
    session.add(row)
    AuditService(session).log(
        "remove.run",
        actor=requested_by or "system",
        resource_type="removal",
        resource_id=row.id,
        detail={"method": method, "asset_id": asset_id},
    )
    session.commit()

    return RemoveResponse(
        method=method,
        watermark_detected=result.watermark_detected_before,
        removal_success=result.removal_success,
        quality_score=result.quality_score,
        output_uri=str(out_path),
    )
