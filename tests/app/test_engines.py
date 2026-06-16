"""Tests for watermark engines: embed/detect, robustness, false positives."""

from __future__ import annotations

import numpy as np
import pytest

from app.core.frequency_watermark import FrequencyWatermarkEngine
from app.core.keyed_gaussian import KeyedGaussianEngine
from app.payload.service import TokenCodec


# Each engine is tested against the JPEG qualities it is designed to survive.
# keyed-gaussian (the primary "custom-noise" engine) is the most robust; the
# block-DCT frequency engine targets lighter recompression (q>=75).
ENGINES = [
    pytest.param(KeyedGaussianEngine, (90, 75, 50), id="keyed-gaussian"),
    pytest.param(FrequencyWatermarkEngine, (90, 75), id="frequency"),
]


@pytest.mark.parametrize("engine_cls, jpeg_qualities", ENGINES)
def test_embed_is_imperceptible(engine_cls, jpeg_qualities, natural_image, key):
    eng = engine_cls()
    tc = TokenCodec()
    wire = tc.encode(tc.new_token_id())
    res = eng.embed(natural_image, wire, key, strength=0.2)
    assert res.psnr > 38.0  # imperceptible
    assert res.ssim > 0.95  # doc target
    assert res.image.shape == natural_image.shape


@pytest.mark.parametrize("engine_cls, jpeg_qualities", ENGINES)
def test_clean_recovery(engine_cls, jpeg_qualities, natural_image, key):
    eng = engine_cls()
    tc = TokenCodec()
    tid = tc.new_token_id()
    wire = tc.encode(tid)
    res = eng.embed(natural_image, wire, key, strength=0.2)
    det = eng.detect(res.image, key, payload_len=len(wire))
    out, crc_ok = tc.decode(det.payload_bytes[: len(wire)])
    assert crc_ok
    assert out == tid


@pytest.mark.parametrize("engine_cls, jpeg_qualities", ENGINES)
def test_jpeg_survival(engine_cls, jpeg_qualities, natural_image, key, jpeg):
    eng = engine_cls()
    tc = TokenCodec()
    tid = tc.new_token_id()
    wire = tc.encode(tid)
    res = eng.embed(natural_image, wire, key, strength=0.22)
    for q in jpeg_qualities:
        det = eng.detect(jpeg(res.image, q), key, payload_len=len(wire))
        out, crc_ok = tc.decode(det.payload_bytes[: len(wire)])
        assert crc_ok and out == tid, f"failed JPEG q={q}"


@pytest.mark.parametrize("engine_cls, jpeg_qualities", ENGINES)
def test_wrong_key_no_false_positive(engine_cls, jpeg_qualities, natural_image, key):
    eng = engine_cls()
    tc = TokenCodec()
    wire = tc.encode(tc.new_token_id())
    res = eng.embed(natural_image, wire, key, strength=0.22)
    det = eng.detect(res.image, b"WRONG-KEY-" + b"0" * 22, payload_len=len(wire))
    _, crc_ok = tc.decode(det.payload_bytes[: len(wire)])
    # Security-critical: a wrong key must never recover a valid (CRC-passing) token.
    assert not crc_ok
    # Raw confidence stays well below the ~0.9 a CRC-confirmed detection yields.
    assert det.confidence < 0.5


@pytest.mark.parametrize("engine_cls, jpeg_qualities", ENGINES)
def test_capacity_enforced(engine_cls, jpeg_qualities, natural_image, key):
    eng = engine_cls()
    too_big = b"\x00" * (eng.capacity_bits(natural_image.shape) // 8 + 50)
    with pytest.raises(ValueError):
        eng.embed(natural_image, too_big, key, strength=0.2)


def test_keyed_gaussian_multi_key(natural_image):
    eng = KeyedGaussianEngine()
    tc = TokenCodec()
    k1, k2 = b"1" * 32, b"2" * 32
    t1, t2 = tc.new_token_id(), tc.new_token_id()
    res = eng.embed_multi(natural_image, {k1: tc.encode(t1), k2: tc.encode(t2)}, strength=0.16)
    # both keyed marks independently recoverable
    d1 = eng.detect(res.image, k1, payload_len=tc.wire_len())
    d2 = eng.detect(res.image, k2, payload_len=tc.wire_len())
    o1, ok1 = tc.decode(d1.payload_bytes[: tc.wire_len()])
    o2, ok2 = tc.decode(d2.payload_bytes[: tc.wire_len()])
    assert ok1 and o1 == t1
    assert ok2 and o2 == t2
