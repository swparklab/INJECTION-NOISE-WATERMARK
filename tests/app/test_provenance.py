"""Tests for registry, hash-chained audit, and C2PA provenance."""

from __future__ import annotations

from app.provenance.audit import AuditService
from app.provenance.c2pa import C2PAService
from app.provenance.registry import RegistryService


def test_registry_delivery_and_lineage(memory_db):
    with memory_db.session_scope() as s:
        reg = RegistryService(s)
        reg.create_asset("A1", "C1", "Title")
        reg.record_delivery("A1", "C1", "r1@x", "D1", "custom-noise", 0.1, b"p1")
        reg.record_delivery("A1", "C1", "r2@x", "D2", "custom-noise", 0.1, b"p2", parent_delivery_id="D1")
        reg.record_delivery("A1", "C1", "r3@x", "D3", "custom-noise", 0.1, b"p3", parent_delivery_id="D2")

    with memory_db.session_scope() as s:
        reg = RegistryService(s)
        assert reg.lineage("D3") == ["MASTER", "D1", "D2", "D3"]
        found = reg.find_delivery_by_fingerprint(b"p3")
        assert found.recipient_id == "r3@x"
        assert reg.list_asset_ids("C1") == ["A1"]


def test_audit_chain_valid(memory_db):
    with memory_db.session_scope() as s:
        aud = AuditService(s)
        aud.log("a.1", resource_id="x")
        aud.log("a.2", resource_id="y")
        aud.log("a.3", resource_id="z")
    with memory_db.session_scope() as s:
        valid, n = AuditService(s).verify_chain()
        assert valid
        assert n == 3


def test_audit_chain_detects_tamper(memory_db):
    from app.db.models import AuditLog

    with memory_db.session_scope() as s:
        aud = AuditService(s)
        aud.log("a.1", resource_id="x")
        aud.log("a.2", resource_id="y")

    # tamper with a historical entry
    s = memory_db.SessionLocal()
    row = s.query(AuditLog).first()
    row.detail = {"tampered": True}
    s.commit()
    s.close()

    with memory_db.session_scope() as s:
        valid, _ = AuditService(s).verify_chain()
        assert not valid


def test_c2pa_manifest_sign_verify():
    c2pa = C2PAService()
    manifest = c2pa.build_manifest("A1", "custom-noise", "D1", "r1@x", "Title")
    assert c2pa.verify_manifest(manifest)
    # tamper a field -> signature invalid
    manifest.recipient_id = "attacker@x"
    assert not c2pa.verify_manifest(manifest)
