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
