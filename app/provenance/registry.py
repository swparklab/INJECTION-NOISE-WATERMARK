"""Registry service: assets, deliveries, and payload-fingerprint lookup.

The registry is the source of truth that lets a recovered payload be resolved
back to a concrete asset / delivery / recipient during a trace investigation.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Asset, Delivery, WatermarkModel


def payload_fingerprint(raw_payload: bytes) -> str:
    """Stable fingerprint of an encoded payload (for fast registry lookup)."""
    return hashlib.sha256(raw_payload).hexdigest()


class RegistryService:
    """CRUD + lookup operations over assets and deliveries."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- models ------------------------------------------------------------
    def upsert_model(
        self,
        model_id: str,
        name: str,
        media_types: list[str],
        description: str = "",
        capacity_bytes: int = 0,
        enabled: bool = True,
    ) -> WatermarkModel:
        """Register or update a watermark model's capability record."""
        obj = self.session.get(WatermarkModel, model_id)
        if obj is None:
            obj = WatermarkModel(id=model_id)
            self.session.add(obj)
        obj.name = name
        obj.media_types = media_types
        obj.description = description
        obj.capacity_bytes = capacity_bytes
        obj.enabled = enabled
        self.session.flush()
        return obj

    def list_models(self, enabled_only: bool = True) -> list[WatermarkModel]:
        """List registered watermark models."""
        stmt = select(WatermarkModel)
        if enabled_only:
            stmt = stmt.where(WatermarkModel.enabled.is_(True))
        return list(self.session.scalars(stmt))

    # -- assets ------------------------------------------------------------
    def create_asset(
        self,
        asset_id: str,
        client_id: str,
        title: str = "",
        media_type: str = "image",
        original_hash: str = "",
        perceptual_hash: str = "",
    ) -> Asset:
        """Create (or return existing) master asset record."""
        obj = self.session.get(Asset, asset_id)
        if obj is None:
            obj = Asset(id=asset_id, client_id=client_id)
            self.session.add(obj)
        obj.title = title or obj.title
        obj.media_type = media_type
        obj.original_hash = original_hash or obj.original_hash
        obj.perceptual_hash = perceptual_hash or obj.perceptual_hash
        self.session.flush()
        return obj

    def list_asset_ids(self, client_id: str | None = None) -> list[str]:
        """Return all asset ids, optionally filtered by client (trace candidates)."""
        stmt = select(Asset.id)
        if client_id:
            stmt = stmt.where(Asset.client_id == client_id)
        return list(self.session.scalars(stmt))

    # -- deliveries --------------------------------------------------------
    def record_delivery(
        self,
        asset_id: str,
        client_id: str,
        recipient_id: str,
        delivery_id: str,
        watermark_model: str,
        strength: float,
        raw_payload: bytes,
        distribution_id: str = "",
        parent_delivery_id: str | None = None,
        output_uri: str = "",
        metadata: dict | None = None,
    ) -> Delivery:
        """Persist a delivery and its payload fingerprint."""
        obj = Delivery(
            id=delivery_id,
            asset_id=asset_id,
            parent_delivery_id=parent_delivery_id,
            client_id=client_id,
            recipient_id=recipient_id,
            distribution_id=distribution_id,
            watermark_model=watermark_model,
            strength=strength,
            payload_fingerprint=payload_fingerprint(raw_payload),
            output_uri=output_uri,
            delivery_metadata=metadata or {},
        )
        self.session.add(obj)
        self.session.flush()
        return obj

    def find_delivery_by_fingerprint(self, raw_payload: bytes) -> Delivery | None:
        """Locate a delivery by exact payload fingerprint."""
        fp = payload_fingerprint(raw_payload)
        stmt = select(Delivery).where(Delivery.payload_fingerprint == fp)
        return self.session.scalars(stmt).first()

    def get_delivery(self, delivery_id: str) -> Delivery | None:
        """Fetch a delivery by id."""
        return self.session.get(Delivery, delivery_id)

    def lineage(self, delivery_id: str) -> list[str]:
        """Walk parent links to build the chain MASTER -> ... -> delivery."""
        path: list[str] = []
        current = self.session.get(Delivery, delivery_id)
        guard = 0
        while current is not None and guard < 1000:
            path.append(current.id)
            if current.parent_delivery_id is None:
                break
            current = self.session.get(Delivery, current.parent_delivery_id)
            guard += 1
        path.append("MASTER")
        return list(reversed(path))
