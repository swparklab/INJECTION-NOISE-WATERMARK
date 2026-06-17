"""Trace endpoints: resolve a suspect file to its leaking delivery/recipient."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_watermark_service
from app.core.tracking_engine import TrackingEngine
from app.core.watermark_engine import WatermarkService
from app.schemas.api import TraceResponse
from app.utils import media
from app.video import io as video_io

router = APIRouter(tags=["trace"])


@router.post("/trace", response_model=TraceResponse)
async def trace_image(
    file: UploadFile = File(...),
    client_id: str | None = Form(None),
    model: str | None = Form(None),
    service: WatermarkService = Depends(get_watermark_service),
    session: Session = Depends(db_session),
) -> TraceResponse:
    """Trace a suspect image to its originating delivery and recipient."""
    raw = await file.read()
    try:
        image = media.decode_image(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tracker = TrackingEngine(session, service)
    result = tracker.trace_image(image, client_id=client_id, model_id=model)
    session.commit()
    return TraceResponse(**result.to_dict())


@router.post("/video/trace", response_model=TraceResponse)
async def trace_video(
    file: UploadFile = File(...),
    client_id: str | None = Form(None),
    model: str = Form("custom-noise"),
    max_frames: int = Form(16),
    roi_x: float = Form(0.0),
    roi_y: float = Form(0.0),
    roi_w: float = Form(1.0),
    roi_h: float = Form(1.0),
    service: WatermarkService = Depends(get_watermark_service),
    session: Session = Depends(db_session),
) -> TraceResponse:
    """Trace a suspect video to its originating delivery via frame voting.

    If the watermark was confined to a region at embed time, supply the same
    ``roi_*`` fractions so each sampled frame is cropped before detection.
    """
    raw = await file.read()
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename or "v.mp4").suffix, delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    frames = video_io.sample_frames(tmp_path, n=max_frames)
    if not frames:
        raise HTTPException(status_code=400, detail="no frames decoded from video")

    if not video_io.is_full_roi(roi_x, roi_y, roi_w, roi_h):
        cropped = []
        for f in frames:
            x0, y0, x1, y1 = video_io.roi_to_pixels(f.shape[0], f.shape[1], roi_x, roi_y, roi_w, roi_h)
            cropped.append(f[y0:y1, x0:x1])
        frames = cropped

    tracker = TrackingEngine(session, service)
    result = tracker.trace_video(frames, client_id=client_id, model_id=model)
    session.commit()
    return TraceResponse(**result.to_dict())
