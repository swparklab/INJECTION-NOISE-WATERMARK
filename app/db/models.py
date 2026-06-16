"""ORM models implementing the platform's database schema.

Covers the tables described in the development document section 9:
    - watermark_models      (available engines / capabilities)
    - assets                (master works)
    - deliveries            (issued copies, with payload + recipient)
    - watermark_traces      (trace/leak investigation results)
    - watermark_removals    (removal operation records)
    - audit_logs            (immutable audit trail)
    - provenance_records    (hashes, C2PA manifest refs, lineage)
    - evidence_reports      (generated forensic/legal evidence)
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class WatermarkModel(Base):
    """Registry of available watermark engines and their capabilities."""

    __tablename__ = "watermark_models"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "videoseal"
    name: Mapped[str] = mapped_column(String(128))
    media_types: Mapped[list] = mapped_column(JSON, default=list)  # ["image","video"]
    description: Mapped[str] = mapped_column(Text, default="")
    capacity_bytes: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Asset(Base):
    """A master work owned by a client/tenant."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    media_type: Mapped[str] = mapped_column(String(16), default="image")
    original_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    perceptual_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    deliveries: Mapped[list["Delivery"]] = relationship(back_populates="asset")


class Delivery(Base):
    """An issued copy of an asset to a specific recipient (leak attribution)."""

    __tablename__ = "deliveries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    parent_delivery_id: Mapped[str | None] = mapped_column(
        ForeignKey("deliveries.id"), nullable=True, index=True
    )
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    recipient_id: Mapped[str] = mapped_column(String(128), index=True)
    distribution_id: Mapped[str] = mapped_column(String(64), default="")
    watermark_model: Mapped[str] = mapped_column(String(64), default="custom-noise")
    strength: Mapped[float] = mapped_column(Float, default=0.12)
    payload_fingerprint: Mapped[str] = mapped_column(String(128), index=True, default="")
    output_uri: Mapped[str] = mapped_column(String(512), default="")
    delivery_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    asset: Mapped["Asset"] = relationship(back_populates="deliveries")


class WatermarkTrace(Base):
    """Result of a trace/leak investigation on a suspect file."""

    __tablename__ = "watermark_traces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    asset_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    delivery_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    recipient_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    watermark_model: Mapped[str] = mapped_column(String(64), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    trace_path: Mapped[list] = mapped_column(JSON, default=list)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class WatermarkRemoval(Base):
    """Record of a watermark removal operation (rights-holder/verifier use)."""

    __tablename__ = "watermark_removals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    asset_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    method: Mapped[str] = mapped_column(String(64), default="")
    watermark_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    removal_success: Mapped[float] = mapped_column(Float, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    requested_by: Mapped[str] = mapped_column(String(128), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    """Immutable audit trail entry (append-only by convention)."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    actor: Mapped[str] = mapped_column(String(128), index=True, default="system")
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), default="")
    resource_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    prev_hash: Mapped[str] = mapped_column(String(128), default="")
    entry_hash: Mapped[str] = mapped_column(String(128), default="", index=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ProvenanceRecord(Base):
    """Provenance / chain-of-custody record for an asset or delivery."""

    __tablename__ = "provenance_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(String(64), index=True)
    delivery_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    original_hash: Mapped[str] = mapped_column(String(128), default="")
    perceptual_hash: Mapped[str] = mapped_column(String(128), default="")
    c2pa_manifest_uri: Mapped[str] = mapped_column(String(512), default="")
    signature: Mapped[str] = mapped_column(Text, default="")
    chain_of_custody: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EvidenceReport(Base):
    """A generated forensic/legal/audit evidence report."""

    __tablename__ = "evidence_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    report_type: Mapped[str] = mapped_column(String(32), default="forensic")
    uri: Mapped[str] = mapped_column(String(512), default="")
    signature: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
