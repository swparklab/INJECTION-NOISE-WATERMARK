"""Integration tests for the FastAPI API via TestClient."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(memory_db):
    """TestClient bound to an isolated DB (memory_db patches the engine)."""
    from app.main import app

    with TestClient(app) as c:
        yield c


def _png_bytes(image: np.ndarray) -> bytes:
    ok, enc = cv2.imencode(".png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    return enc.tobytes()


def _jpeg_bytes(image: np.ndarray, q: int = 60) -> bytes:
    ok, enc = cv2.imencode(".jpg", cv2.cvtColor(image, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, q])
    return enc.tobytes()


def test_health_and_models(client):
    assert client.get("/health").json()["status"] == "ok"
    models = client.get("/api/v1/models").json()
    assert "custom-noise" in models["models"]
    assert "videoseal" in models["models"]


def test_embed_then_trace_flow(client, natural_image):
    png = _png_bytes(natural_image)

    # embed
    r = client.post(
        "/api/v1/embed",
        files={"file": ("master.png", png, "image/png")},
        data={
            "asset_id": "ASSET-API",
            "client_id": "CLIENT-A",
            "recipient_id": "leaker@x.com",
            "model": "custom-noise",
            "strength": "0.22",
            "distribution_id": "OTT",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["psnr"] > 38
    assert body["ssim"] > 0.95
    delivery_id = body["delivery_id"]

    # read back the watermarked output and simulate a JPEG leak
    out = cv2.cvtColor(cv2.imread(body["output_uri"]), cv2.COLOR_BGR2RGB)
    leak = _jpeg_bytes(out, 60)

    # trace
    r = client.post(
        "/api/v1/trace",
        files={"file": ("leak.jpg", leak, "image/jpeg")},
        data={"client_id": "CLIENT-A"},
    )
    assert r.status_code == 200, r.text
    trace = r.json()
    assert trace["found"]
    assert trace["recipient"] == "leaker@x.com"
    assert trace["delivery_id"] == delivery_id
    assert trace["signature_valid"]


def test_detect_endpoint(client, natural_image):
    png = _png_bytes(natural_image)
    r = client.post(
        "/api/v1/embed",
        files={"file": ("m.png", png, "image/png")},
        data={"asset_id": "ASSET-D", "client_id": "C", "recipient_id": "r@x", "model": "custom-noise"},
    )
    out = cv2.cvtColor(cv2.imread(r.json()["output_uri"]), cv2.COLOR_BGR2RGB)
    r = client.post(
        "/api/v1/detect",
        files={"file": ("w.png", _png_bytes(out), "image/png")},
        data={"asset_id": "ASSET-D", "model": "custom-noise"},
    )
    assert r.status_code == 200
    assert r.json()["detected"]
    assert r.json()["crc_ok"]


def test_audit_verify_endpoint(client, natural_image):
    png = _png_bytes(natural_image)
    client.post(
        "/api/v1/embed",
        files={"file": ("m.png", png, "image/png")},
        data={"asset_id": "ASSET-AU", "client_id": "C", "recipient_id": "r@x"},
    )
    r = client.get("/api/v1/audit/verify")
    assert r.status_code == 200
    assert r.json()["valid"]
    assert r.json()["entries"] >= 1


def test_remove_endpoint(client, natural_image):
    png = _png_bytes(natural_image)
    r = client.post(
        "/api/v1/embed",
        files={"file": ("m.png", png, "image/png")},
        data={"asset_id": "ASSET-R", "client_id": "C", "recipient_id": "r@x"},
    )
    out = cv2.cvtColor(cv2.imread(r.json()["output_uri"]), cv2.COLOR_BGR2RGB)
    r = client.post(
        "/api/v1/remove",
        files={"file": ("w.png", _png_bytes(out), "image/png")},
        data={"method": "frequency_suppression", "asset_id": "ASSET-R", "model": "custom-noise"},
    )
    assert r.status_code == 200
    assert 0.0 <= r.json()["quality_score"] <= 1.0
