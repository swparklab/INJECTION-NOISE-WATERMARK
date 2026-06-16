"""Tests for the end-to-end tracking, removal, and evidence flows."""

from __future__ import annotations

import numpy as np

from app.core.removal_engine import RemovalEngine
from app.core.tracking_engine import TrackingEngine
from app.core.watermark_engine import WatermarkService
from app.payload.service import TokenCodec
from app.provenance.registry import RegistryService
from app.reports.evidence import EvidenceService


def _embed_and_register(memory_db, image, service, *, asset="A1", recipient="leaker@x") -> str:
    tc = TokenCodec()
    with memory_db.session_scope() as s:
        reg = RegistryService(s)
        reg.create_asset(asset, "C1", "Film")
        out = service.embed_image(image, asset, "custom-noise", strength=0.22)
        reg.record_delivery(
            asset, "C1", recipient, "D1", "custom-noise", 0.22, tc.encode(out.token_id), "OTT"
        )
    return out  # EmbedOutcome


def test_trace_identifies_recipient_after_jpeg(memory_db, registered_engines, natural_image, jpeg):
    service = WatermarkService()
    out = _embed_and_register(memory_db, natural_image, service)
    leaked = jpeg(out.image, 60)

    with memory_db.session_scope() as s:
        tracker = TrackingEngine(s, service)
        result = tracker.trace_image(leaked, client_id="C1")

    assert result.found
    assert result.recipient_id == "leaker@x"
    assert result.delivery_id == "D1"
    assert result.signature_valid
    assert result.trace_path == ["MASTER", "D1"]


def test_trace_unknown_image_returns_not_found(memory_db, registered_engines, natural_image):
    service = WatermarkService()
    # register a delivery for a different asset/image, then trace a clean image
    _embed_and_register(memory_db, natural_image, service)
    clean = np.full_like(natural_image, 128)

    with memory_db.session_scope() as s:
        tracker = TrackingEngine(s, service)
        result = tracker.trace_image(clean, client_id="C1")
    assert not result.found


def test_evidence_report_is_signed(memory_db, registered_engines, natural_image, jpeg):
    service = WatermarkService()
    out = _embed_and_register(memory_db, natural_image, service)
    leaked = jpeg(out.image, 70)

    with memory_db.session_scope() as s:
        tracker = TrackingEngine(s, service)
        result = tracker.trace_image(leaked, client_id="C1")
        ev = EvidenceService(s, now=None)
        report = ev.generate(result, "forensic", timestamp="2026-06-17T00:00:00Z")
        assert ev.verify(report)
        assert report.audit_chain_valid
        assert any("leaker@x" in s for s in report.statements)


def test_removal_reduces_detectability(memory_db, registered_engines, natural_image):
    service = WatermarkService()
    tc = TokenCodec()
    key = service._key_for_asset("A1")
    out = service.embed_image(natural_image, "A1", "custom-noise", strength=0.22)

    engine = RemovalEngine()
    res = engine.remove(
        out.image, method="template_cancellation", key=key, model_id="custom-noise",
        wire_len=tc.wire_len(),
    )
    assert res.watermark_detected_before
    assert res.quality_score > 0.9  # host preserved
    # after template cancellation the token should no longer cleanly decode
    det = service.detect_image(res.image, "A1", "custom-noise")
    assert not det.crc_ok or det.confidence < out.detail.get("raw_confidence", 1.0)


def test_isolation_returns_noise_layer(registered_engines, natural_image):
    service = WatermarkService()
    out = service.embed_image(natural_image, "A1", "custom-noise", strength=0.22)
    engine = RemovalEngine()
    res = engine.remove(out.image, method="watermark_isolation", key=None, model_id="custom-noise")
    assert res.isolated_watermark is not None
    assert res.isolated_watermark.shape == natural_image.shape
