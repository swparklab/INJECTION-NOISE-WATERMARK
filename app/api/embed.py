"""Embed endpoints: watermark an image/video and register the delivery."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_watermark_service
from app.config.settings import get_settings
from app.core.watermark_engine import WatermarkService
from app.payload.service import TokenCodec
from app.provenance.audit import AuditService
from app.provenance.c2pa import C2PAService
from app.provenance.registry import RegistryService
from app.schemas.api import EmbedResponse
from app.utils import media
from app.utils.hashing import content_hash, perceptual_hash

router = APIRouter(tags=["embed"])


@router.post("/embed", response_model=EmbedResponse)
async def embed_image(
    file: UploadFile = File(...),
    asset_id: str = Form(...),
    client_id: str = Form(...),
    recipient_id: str = Form(...),
    delivery_id: str | None = Form(None),
    model: str = Form("custom-noise"),
    strength: float = Form(0.18),
    distribution_id: str = Form(""),
    parent_delivery_id: str | None = Form(None),
    title: str = Form(""),
    service: WatermarkService = Depends(get_watermark_service),
    session: Session = Depends(db_session),
) -> EmbedResponse:
    """Embed a watermark into an uploaded image and register the delivery.

    Returns the delivery id and the URI of the watermarked output.
    """
    settings = get_settings()
    raw = await file.read()
    try:
        image = media.decode_image(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    delivery_id = delivery_id or str(uuid.uuid4())
    reg = RegistryService(session)
    audit = AuditService(session)
    tc = TokenCodec()

    # Ensure the asset exists with hashes.
    reg.create_asset(
        asset_id,
        client_id,
        title=title,
        original_hash=content_hash(raw),
        perceptual_hash=perceptual_hash(image),
    )

    try:
        outcome = service.embed_image(image, asset_id, model, strength)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Persist watermarked output.
    out_dir = Path(settings.data_dir) / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{delivery_id}.png"
    out_path.write_bytes(media.encode_image(outcome.image, ".png"))

    # C2PA manifest sidecar.
    c2pa = C2PAService()
    manifest = c2pa.build_manifest(
        asset_id, model, delivery_id, recipient_id, title
    )
    manifest_path = out_dir / f"{delivery_id}.c2pa.json"
    c2pa.write_sidecar(manifest, str(manifest_path))

    reg.record_delivery(
        asset_id=asset_id,
        client_id=client_id,
        recipient_id=recipient_id,
        delivery_id=delivery_id,
        watermark_model=model,
        strength=strength,
        raw_payload=tc.encode(outcome.token_id),
        distribution_id=distribution_id,
        parent_delivery_id=parent_delivery_id,
        output_uri=str(out_path),
    )
    audit.log(
        "embed.create",
        actor=client_id,
        resource_type="delivery",
        resource_id=delivery_id,
        detail={"model": model, "recipient": recipient_id},
    )
    session.commit()

    return EmbedResponse(
        delivery_id=delivery_id,
        asset_id=asset_id,
        token_id=outcome.token_id.hex(),
        model=model,
        psnr=round(outcome.psnr, 2),
        ssim=round(outcome.ssim, 4),
        output_uri=str(out_path),
        c2pa_manifest_uri=str(manifest_path),
    )


@router.post("/video/embed", response_model=EmbedResponse)
async def embed_video(
    file: UploadFile = File(...),
    asset_id: str = Form(...),
    client_id: str = Form(...),
    recipient_id: str = Form(...),
    delivery_id: str | None = Form(None),
    model: str = Form("custom-noise"),
    strength: float = Form(0.3),
    distribution_id: str = Form(""),
    parent_delivery_id: str | None = Form(None),
    title: str = Form(""),
    roi_x: float = Form(0.0),
    roi_y: float = Form(0.0),
    roi_w: float = Form(1.0),
    roi_h: float = Form(1.0),
    start_sec: float = Form(0.0),
    end_sec: float = Form(-1.0),
    service: WatermarkService = Depends(get_watermark_service),
    session: Session = Depends(db_session),
) -> EmbedResponse:
    """Embed a watermark token into an uploaded video.

    The mark can be confined to a **spatial region** (``roi_*`` fractions of the
    frame) and a **time range** (``start_sec``..``end_sec``; ``end_sec<0`` = to
    the end). Frames outside the time range are left untouched; within range the
    token is embedded into the chosen ROI of each frame. Detection later uses
    majority frame-voting (the same ROI must be supplied when reading).
    """
    import tempfile

    from app.core import registry as engine_registry
    from app.payload.service import TokenCodec
    from app.video import io as video_io

    settings = get_settings()
    raw = await file.read()
    suffix = Path(file.filename or "in.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        in_path = tmp.name

    frames = list(video_io.read_frames(in_path))
    if not frames:
        raise HTTPException(status_code=400, detail="no frames decoded from video")
    fps = video_io.probe_fps(in_path)

    delivery_id = delivery_id or str(uuid.uuid4())
    tc = TokenCodec()
    token_id = tc.new_token_id()
    wire = tc.encode(token_id)
    key = service._key_for_asset(asset_id)

    try:
        engine = engine_registry.get_engine(model)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    full_roi = video_io.is_full_roi(roi_x, roi_y, roi_w, roi_h)
    end = end_sec if end_sec >= 0 else (len(frames) / fps + 1.0)

    psnrs: list[float] = []
    wm_frames = []
    embedded = 0
    for i, frame in enumerate(frames):
        t = i / fps
        if not (start_sec <= t <= end):
            wm_frames.append(frame)
            continue
        try:
            if full_roi:
                res = engine.embed(frame, wire, key, strength)
                out_frame = res.image
            else:
                x0, y0, x1, y1 = video_io.roi_to_pixels(
                    frame.shape[0], frame.shape[1], roi_x, roi_y, roi_w, roi_h
                )
                res = engine.embed(frame[y0:y1, x0:x1], wire, key, strength)
                out_frame = frame.copy()
                out_frame[y0:y1, x0:x1] = res.image
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    "선택한 영역이 너무 작아 워터마크 토큰을 넣을 수 없습니다. "
                    "영역을 넓히거나 더 높은 해상도의 영상을 사용하세요. "
                    f"({exc})"
                ),
            ) from exc
        psnrs.append(res.psnr)
        wm_frames.append(out_frame)
        embedded += 1

    if embedded == 0:
        raise HTTPException(status_code=400, detail="지정한 시간 구간에 해당하는 프레임이 없습니다")

    out_dir = Path(settings.data_dir) / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{delivery_id}.mp4"
    # High-quality encode (crf 16) so the low-amplitude mark survives this encode.
    video_io.write_frames(out_path, wm_frames, fps=fps, codec="libx264", crf=16)

    roi_meta = {"x": roi_x, "y": roi_y, "w": roi_w, "h": roi_h}
    reg = RegistryService(session)
    reg.create_asset(asset_id, client_id, title=title, media_type="video")
    reg.record_delivery(
        asset_id=asset_id,
        client_id=client_id,
        recipient_id=recipient_id,
        delivery_id=delivery_id,
        watermark_model=model,
        strength=strength,
        raw_payload=wire,
        distribution_id=distribution_id,
        parent_delivery_id=parent_delivery_id,
        output_uri=str(out_path),
        metadata={
            "media_type": "video",
            "frames": len(frames),
            "embedded_frames": embedded,
            "fps": fps,
            "roi": roi_meta,
            "time_range": [start_sec, None if end_sec < 0 else end_sec],
        },
    )
    AuditService(session).log(
        "embed.video",
        actor=client_id,
        resource_type="delivery",
        resource_id=delivery_id,
        detail={
            "model": model,
            "recipient": recipient_id,
            "frames": len(frames),
            "embedded_frames": embedded,
            "roi": roi_meta,
        },
    )
    session.commit()

    avg_psnr = round(sum(psnrs) / len(psnrs), 2) if psnrs else 0.0
    return EmbedResponse(
        delivery_id=delivery_id,
        asset_id=asset_id,
        token_id=token_id.hex(),
        model=model,
        psnr=avg_psnr,
        ssim=0.0,
        output_uri=str(out_path),
    )
