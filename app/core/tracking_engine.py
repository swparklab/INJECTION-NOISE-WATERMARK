"""Tracking engine: resolve a detected watermark to a leak source.

Implements the trace flow from the development document section 7.5::

    model identification -> payload/token extraction -> registry lookup
    -> asset history -> recipient match -> leak-path analysis -> lineage graph

Given a suspect image/video, it determines which delivery (and therefore which
recipient) the leaked copy originated from, with a confidence score and a
chain-of-custody lineage path suitable for an evidence report.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sqlalchemy.orm import Session

from app.core.watermark_engine import WatermarkService
from app.provenance.audit import AuditService
from app.provenance.registry import RegistryService


@dataclass
class TraceResult:
    """Outcome of a trace investigation."""

    found: bool
    asset_id: str | None = None
    delivery_id: str | None = None
    recipient_id: str | None = None
    client_id: str | None = None
    watermark_model: str | None = None
    confidence: float = 0.0
    signature_valid: bool = False
    trace_path: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialise to a plain dict (API / report friendly)."""
        return {
            "found": self.found,
            "asset_id": self.asset_id,
            "delivery_id": self.delivery_id,
            "recipient": self.recipient_id,
            "client_id": self.client_id,
            "watermark_model": self.watermark_model,
            "confidence": round(self.confidence, 4),
            "signature_valid": self.signature_valid,
            "trace_path": self.trace_path,
            "detail": self.detail,
        }


class TrackingEngine:
    """Resolve detections to deliveries/recipients and build lineage graphs."""

    def __init__(self, session: Session, service: WatermarkService | None = None) -> None:
        self.session = session
        self.service = service or WatermarkService()
        self.registry = RegistryService(session)
        self.audit = AuditService(session)

    # -- image -------------------------------------------------------------
    def trace_image(
        self,
        image: np.ndarray,
        client_id: str | None = None,
        model_id: str | None = None,
    ) -> TraceResult:
        """Trace a suspect image to its originating delivery.

        Args:
            image: The leaked / suspect RGB image.
            client_id: Restrict candidate assets to a client (faster, fewer FPs).
            model_id: Restrict to a known model, else try all.

        Returns:
            TraceResult with the resolved recipient and lineage path.
        """
        candidate_assets = self.registry.list_asset_ids(client_id)
        models = [model_id] if model_id else None

        hit = self.service.detect_image_blind(image, candidate_assets, models)
        if hit is None:
            return self._record_trace(TraceResult(found=False))

        asset_id, det = hit
        if not det.crc_ok or det.token_id is None:
            return self._record_trace(
                TraceResult(found=False, asset_id=asset_id, confidence=det.confidence)
            )

        return self._resolve_token(asset_id, det.token_id, det.model_id, det.confidence)

    # -- video -------------------------------------------------------------
    def trace_video(
        self,
        frames: list[np.ndarray],
        client_id: str | None = None,
        model_id: str = "custom-noise",
    ) -> TraceResult:
        """Trace a suspect video via frame-vote detection across candidate assets."""
        candidate_assets = self.registry.list_asset_ids(client_id)
        for asset_id in candidate_assets:
            det = self.service.detect_video(frames, asset_id, model_id)
            if det.crc_ok and det.token_id:
                return self._resolve_token(asset_id, det.token_id, det.model_id, det.confidence)
        return self._record_trace(TraceResult(found=False))

    # -- helpers -----------------------------------------------------------
    def _resolve_token(
        self, asset_id: str, token_id: bytes, model_id: str, confidence: float
    ) -> TraceResult:
        """Look up the delivery for a recovered token and build lineage."""
        from app.payload.service import TokenCodec

        wire = TokenCodec().encode(token_id)  # canonical fingerprint of the token
        delivery = self.registry.find_delivery_by_fingerprint(wire)
        if delivery is None:
            return self._record_trace(
                TraceResult(
                    found=False,
                    asset_id=asset_id,
                    watermark_model=model_id,
                    confidence=confidence,
                    detail={"reason": "token not in registry", "token": token_id.hex()},
                )
            )

        lineage = self.registry.lineage(delivery.id)
        result = TraceResult(
            found=True,
            asset_id=delivery.asset_id,
            delivery_id=delivery.id,
            recipient_id=delivery.recipient_id,
            client_id=delivery.client_id,
            watermark_model=model_id,
            confidence=confidence,
            signature_valid=True,
            trace_path=lineage,
            detail={"token": token_id.hex(), "distribution_id": delivery.distribution_id},
        )
        return self._record_trace(result)

    def _record_trace(self, result: TraceResult) -> TraceResult:
        """Persist the trace and append an audit entry."""
        from app.db.models import WatermarkTrace

        row = WatermarkTrace(
            asset_id=result.asset_id,
            delivery_id=result.delivery_id,
            recipient_id=result.recipient_id,
            watermark_model=result.watermark_model or "",
            confidence=result.confidence,
            signature_valid=result.signature_valid,
            trace_path=result.trace_path,
            detail=result.detail,
        )
        self.session.add(row)
        self.session.flush()
        result.detail["trace_id"] = row.id
        self.audit.log(
            "trace.run",
            actor="tracking-engine",
            resource_type="trace",
            resource_id=row.id,
            detail={"found": result.found, "recipient": result.recipient_id},
        )
        return result
