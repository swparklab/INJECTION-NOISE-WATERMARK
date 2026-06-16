"""Pydantic request/response schemas for the public API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# -- models ----------------------------------------------------------------
class ModelInfo(BaseModel):
    """Watermark model capability descriptor."""

    id: str
    name: str
    media_types: list[str]
    description: str = ""


class ModelsResponse(BaseModel):
    """Response for GET /models."""

    models: list[str]
    details: list[ModelInfo] = Field(default_factory=list)


# -- embed -----------------------------------------------------------------
class EmbedRequest(BaseModel):
    """Embed request (image bytes sent as multipart; metadata here)."""

    asset_id: str
    client_id: str
    recipient_id: str
    delivery_id: str | None = None
    model: str = "custom-noise"
    strength: float = 0.18
    distribution_id: str = ""
    parent_delivery_id: str | None = None
    title: str = ""


class EmbedResponse(BaseModel):
    """Response for POST /embed."""

    delivery_id: str
    asset_id: str
    token_id: str
    model: str
    psnr: float
    ssim: float
    output_uri: str
    c2pa_manifest_uri: str = ""


# -- detect ----------------------------------------------------------------
class DetectRequest(BaseModel):
    """Detect request metadata."""

    asset_id: str
    model: str = "custom-noise"


class DetectResponse(BaseModel):
    """Response for POST /detect."""

    detected: bool
    confidence: float
    token_id: str | None = None
    crc_ok: bool = False
    model: str = ""


# -- trace -----------------------------------------------------------------
class TraceRequest(BaseModel):
    """Trace request metadata."""

    client_id: str | None = None
    model: str | None = None


class TraceResponse(BaseModel):
    """Response for POST /trace (mirrors TraceResult)."""

    found: bool
    asset_id: str | None = None
    delivery_id: str | None = None
    recipient: str | None = None
    client_id: str | None = None
    watermark_model: str | None = None
    confidence: float = 0.0
    signature_valid: bool = False
    trace_path: list[str] = Field(default_factory=list)
    detail: dict = Field(default_factory=dict)


# -- remove ----------------------------------------------------------------
class RemoveRequest(BaseModel):
    """Remove request metadata."""

    method: str = "frequency_suppression"
    asset_id: str | None = None
    model: str = "custom-noise"
    requested_by: str = ""


class RemoveResponse(BaseModel):
    """Response for POST /remove."""

    method: str
    watermark_detected: bool
    removal_success: float
    quality_score: float
    output_uri: str = ""


# -- provenance / evidence -------------------------------------------------
class ProvenanceVerifyResponse(BaseModel):
    """Response for POST /provenance/verify."""

    valid: bool
    asset_id: str = ""
    watermark_model: str = ""
    detail: dict = Field(default_factory=dict)


class EvidenceResponse(BaseModel):
    """Response for POST /evidence/generate."""

    report_type: str
    generated_at: str
    signature: str
    public_key: str
    audit_chain_valid: bool
    statements: list[str]
    trace: dict


class AuditVerifyResponse(BaseModel):
    """Response for GET /audit/verify."""

    valid: bool
    entries: int
