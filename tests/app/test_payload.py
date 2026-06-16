"""Tests for the payload subsystem: crypto, ECC, signatures, token codec."""

from __future__ import annotations

import pytest

from app.payload import crypto
from app.payload.service import PayloadService, TokenCodec, WatermarkPayload


# -- crypto ----------------------------------------------------------------
def test_derive_key_deterministic_and_context_separated():
    master = b"m" * 32
    k1 = crypto.derive_key(master, "ctx:a")
    k2 = crypto.derive_key(master, "ctx:a")
    k3 = crypto.derive_key(master, "ctx:b")
    assert k1 == k2  # deterministic
    assert k1 != k3  # domain separation
    assert len(k1) == 32


def test_derive_key_rejects_short_master():
    with pytest.raises(ValueError):
        crypto.derive_key(b"short", "ctx")


def test_keystream_deterministic():
    k = b"x" * 32
    assert crypto.keystream(k, 100) == crypto.keystream(k, 100)
    assert len(crypto.keystream(k, 100)) == 100


def test_signature_roundtrip():
    kp = crypto.SignatureKeyPair.generate()
    msg = b"evidence bytes"
    sig = crypto.sign(kp.private_bytes, msg)
    assert crypto.verify(kp.public_bytes, msg, sig)
    assert not crypto.verify(kp.public_bytes, b"tampered", sig)


def test_signature_keypair_from_master_is_deterministic():
    master = b"m" * 32
    a = crypto.SignatureKeyPair.from_master(master)
    b = crypto.SignatureKeyPair.from_master(master)
    assert a.public_bytes == b.public_bytes


# -- payload service -------------------------------------------------------
def _payload() -> WatermarkPayload:
    return WatermarkPayload(
        asset_id="ASSET-1",
        client_id="CLIENT-A",
        delivery_id="DELIVERY-1",
        recipient_id="user@corp.com",
    )


def test_payload_encode_decode_roundtrip():
    svc = PayloadService()
    raw = svc.encode(_payload())
    decoded, sig_ok = svc.decode(raw, asset_id_hint="ASSET-1")
    assert sig_ok
    assert decoded.recipient_id == "user@corp.com"


def test_payload_wrong_key_rejected():
    svc = PayloadService()
    raw = svc.encode(_payload())
    with pytest.raises(ValueError):
        svc.decode(raw, asset_id_hint="WRONG-ASSET")


def test_payload_ecc_recovers_corruption():
    svc = PayloadService()
    raw = bytearray(svc.encode(_payload()))
    for i in range(6):  # corrupt several spread-out bytes
        raw[i * 4] ^= 0xFF
    decoded, sig_ok = svc.decode(bytes(raw), asset_id_hint="ASSET-1")
    assert decoded.recipient_id == "user@corp.com"
    assert sig_ok


def test_payload_decode_with_candidate_keys():
    svc = PayloadService()
    raw = svc.encode(_payload())
    res = svc.decode_with_keys(raw, ["NOPE", "ASSET-1", "ALSO-NO"])
    assert res is not None
    assert res[0].recipient_id == "user@corp.com"


# -- token codec -----------------------------------------------------------
def test_token_codec_roundtrip():
    tc = TokenCodec()
    tid = tc.new_token_id()
    wire = tc.encode(tid)
    out, crc_ok = tc.decode(wire)
    assert crc_ok
    assert out == tid


def test_token_codec_corrects_errors():
    tc = TokenCodec()
    tid = tc.new_token_id()
    wire = bytearray(tc.encode(tid))
    wire[0] ^= 0xFF
    wire[5] ^= 0xFF
    out, crc_ok = tc.decode(bytes(wire))
    assert crc_ok
    assert out == tid


def test_token_codec_detects_uncorrectable():
    tc = TokenCodec(token_bytes=6, parity_bytes=4)
    tid = tc.new_token_id()
    wire = bytearray(tc.encode(tid))
    for i in range(len(wire)):  # destroy everything
        wire[i] ^= 0xAA
    out, crc_ok = tc.decode(bytes(wire))
    assert not crc_ok or out != tid
