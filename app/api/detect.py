"""Detect endpoints: check whether media carries a watermark for an asset."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import get_watermark_service
from app.core.watermark_engine import WatermarkService
from app.schemas.api import DetectResponse
from app.utils import media
from app.video import io as video_io

router = APIRouter(tags=["detect"])


@router.post("/detect", response_model=DetectResponse)
async def detect_image(
    file: UploadFile = File(...),
    asset_id: str = Form(...),
    model: str = Form("custom-noise"),
    service: WatermarkService = Depends(get_watermark_service),
) -> DetectResponse:
    """Detect a watermark in an uploaded image for a known asset + model."""
    raw = await file.read()
    try:
        image = media.decode_image(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    det = service.detect_image(image, asset_id, model)
    return DetectResponse(
        detected=det.detected,
        confidence=round(det.confidence, 4),
        token_id=det.token_id.hex() if det.token_id else None,
        crc_ok=det.crc_ok,
        model=det.model_id,
    )


@router.post("/video/detect", response_model=DetectResponse)
async def detect_video(
    file: UploadFile = File(...),
    asset_id: str = Form(...),
    model: str = Form("custom-noise"),
    max_frames: int = Form(16),
    service: WatermarkService = Depends(get_watermark_service),
) -> DetectResponse:
    """Detect a watermark across sampled video frames via majority vote."""
    import tempfile
    from pathlib import Path

    raw = await file.read()
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename or "v.mp4").suffix, delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    frames = video_io.sample_frames(tmp_path, n=max_frames)
    if not frames:
        raise HTTPException(status_code=400, detail="no frames decoded from video")

    det = service.detect_video(frames, asset_id, model)
    return DetectResponse(
        detected=det.detected,
        confidence=round(det.confidence, 4),
        token_id=det.token_id.hex() if det.token_id else None,
        crc_ok=det.crc_ok,
        model=det.model_id,
    )
