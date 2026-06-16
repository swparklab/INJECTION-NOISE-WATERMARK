# INJECTION-NOISE-WATERMARK

Enterprise invisible-watermark platform for content provenance, leak tracing, and rights protection.

**INJECTION-NOISE-WATERMARK** embeds imperceptible, key-controlled watermarks into images and video, then lets rights holders **detect**, **trace** (attribute a leaked copy to a specific recipient), **verify**, and — for the rights holder — **remove / isolate** those marks. It is the inverse of noise-separation: instead of removing noise, it injects a structured, recoverable noise signature.

Built on top of the original Tree-Ring research code (kept as one of several pluggable engines), the platform combines classical signal-domain watermarking, neural/diffusion adapters, cryptographic payloads, a provenance registry, a tamper-evident audit trail, C2PA content credentials, and a signed evidence platform — behind a single FastAPI service.

> Developed by **Park Seong-Woo** / AIMZ Media.

---

## Why

Content companies that deliver originals (OTT, broadcasters, studios, agencies) need to:

- **Trace leaks** — identify exactly which delivery/recipient a leaked file came from.
- **Prove ownership & credentials** — bind cryptographic provenance to each copy.
- **Stay invisible** — marks must be imperceptible to viewers yet survive re-encoding.
- **Produce evidence** — generate signed, court-admissible forensic reports.

---

## Highlights

- **8 watermark layers** behind one model selector: Keyed Gaussian Noise, Frequency-domain (DCT/DWT), Latent-domain diffusion (Tree-Ring / Gaussian Shading / RingID), Neural (VideoSeal / Meta Seal / InvisMark / WAM), plus video tracking, removal, provenance registry, and C2PA verification.
- **Compact, robust payloads** — AES-GCM encryption + Reed-Solomon ECC + Ed25519 signatures + HKDF key derivation. The watermark carries only a small ECC-protected token; the registry resolves it to the full delivery.
- **Blind detection** — no original needed. Image and video (majority frame-vote) detection with z-score confidence and ECC token recovery.
- **Leak tracing** — recovered token → registry → recipient + chain-of-custody lineage graph.
- **Removal / forensic isolation** — frequency suppression, neural denoising, keyed template cancellation, residual reconstruction, watermark isolation ("noise separation" view).
- **Tamper-evident audit** — hash-chained, append-only log; any modification is detectable.
- **Signed evidence reports** — forensic / legal / audit, independently verifiable.
- **Production posture** — KMS/HSM key-provider abstraction, PostgreSQL/SQLite, S3/MinIO, FastAPI, Docker/K8s-ready.

### Validated performance (natural images)

| Metric | Result | Doc target |
|---|---|---|
| Imperceptibility | PSNR ~48 dB, SSIM ~0.99 | SSIM ≥ 0.95 |
| Clean recovery | 100% | — |
| JPEG 90 / 75 / 50 survival | 100% | ≥ 90% |
| False positive (wrong key) | 0% | — |
| Test suite | 49 passing, 89% platform coverage | — |

---

## Architecture

```
                   Admin / Client / Partner / Legal Portals
                                   │
                                FastAPI  (app/api)
   embed · detect · trace · remove · provenance/verify · evidence · models · audit
                                   │
   ┌───────────────┬──────────────┼───────────────┬────────────────┐
   ▼               ▼              ▼                ▼                ▼
 Payload        Watermark     Detection         Tracking         Removal
 (crypto+ECC    Engines       Engine            Engine           Engine
  +signature)   (selector)    (blind, vote)     (leak→recipient) (5 methods)
   │               │              │                │                │
   └───────────────┴──────────────┴───────────────┴────────────────┘
                                   │
            Provenance: Registry · hash-chained Audit · C2PA
                                   │
                Evidence Platform (signed reports)  ·  DB (SQLAlchemy)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full component map and data flows, and [docs/API.md](docs/API.md) for the endpoint reference.

---

## Quick start

```bash
# 1. Install (core platform deps)
pip install -e .

# 2. Run the API
uvicorn app.main:app --reload

# 3. Open the interactive docs
#    http://127.0.0.1:8000/docs
```

### Embed → leak → trace (cURL)

```bash
# Embed a watermark and register the delivery
curl -X POST http://127.0.0.1:8000/api/v1/embed \
  -F file=@master.png \
  -F asset_id=ASSET-001 -F client_id=CLIENT-A \
  -F recipient_id=studio@partner.com -F model=custom-noise -F strength=0.2

# ... a copy leaks and is re-encoded to JPEG ...

# Trace the leaked file back to its recipient
curl -X POST http://127.0.0.1:8000/api/v1/trace \
  -F file=@leaked.jpg -F client_id=CLIENT-A
# => { "found": true, "recipient": "studio@partner.com",
#      "delivery_id": "...", "signature_valid": true,
#      "trace_path": ["MASTER", "DELIVERY-..."] }
```

### Python SDK

```python
import cv2
from app.core import registry as engines
from app.core.watermark_engine import WatermarkService

engines.register_builtin_engines()
svc = WatermarkService()

img = cv2.cvtColor(cv2.imread("master.png"), cv2.COLOR_BGR2RGB)
out = svc.embed_image(img, asset_id="ASSET-001", model_id="custom-noise", strength=0.2)
print(out.token_id.hex(), out.psnr, out.ssim)

det = svc.detect_image(out.image, asset_id="ASSET-001", model_id="custom-noise")
print(det.detected, det.confidence, det.token_id.hex())
```

---

## Watermark models

| id | name | media | notes |
|---|---|---|---|
| `custom-noise` | Keyed Gaussian Noise | image, video | Primary engine — spread spectrum, multi-key, anti-collusion |
| `frequency` | Frequency-domain | image | Block-DCT + DWT, perceptual masking |
| `tree-ring` | Tree-Ring | image | Diffusion latent Fourier mark (AI-generated) |
| `gaussian-shading` | Gaussian Shading | image | Performance-lossless diffusion watermark |
| `ringid` | RingID | image | Multi-key ring identification |
| `videoseal` | VideoSeal | video, image | Neural video watermark |
| `metaseal` | Meta Seal | image, video | Neural watermark |
| `invismark` | InvisMark | image | High-resolution invisible mark |
| `wam` | Watermark Anything | image | Localized / partial detection |

Neural & diffusion adapters auto-detect their native backend; when absent they fall back to the platform's robust internal engine (flagged `backend="fallback"`), so every model id is operational out-of-the-box.

---

## Project layout

```
app/
  api/         FastAPI routers (embed, detect, trace, remove, verify, models)
  core/        engines (frequency, keyed_gaussian) + detection/tracking/removal/service + selector
  adapters/    neural + diffusion backend adapters
  payload/     crypto, key provider (KMS/HSM), ECC payload + compact token codec
  provenance/  registry, hash-chained audit, C2PA
  reports/     signed evidence platform
  db/          SQLAlchemy models + session
  video/       frame I/O
  config/      settings
src/tree_ring_watermark/   original research code (absorbed as the tree-ring engine)
tests/app/     platform test suite
docs/          ARCHITECTURE.md, API.md
```

---

## Configuration

All settings are environment variables prefixed `INW_` (see `app/config/settings.py`):

| var | default | purpose |
|---|---|---|
| `INW_ENVIRONMENT` | `development` | deployment env |
| `INW_REGISTRY_DB_URL` | `sqlite:///./_data/registry.db` | registry DB (use PostgreSQL in prod) |
| `INW_KMS_PROVIDER` | `local` | `local` \| `vault` \| `aws_kms` \| `hsm` |
| `INW_MASTER_KEY_HEX` | _(dev key)_ | master key material (supply via KMS in prod) |
| `INW_S3_*` | — | object storage (S3/MinIO) |
| `INW_REDIS_URL` | `redis://localhost:6379/0` | cache/queue |

> The default local key is clearly marked insecure — configure a real KMS/HSM-backed key for production.

---

## Testing

```bash
pip install -e ".[dev]"
pytest tests/app/ -q                       # platform suite
pytest tests/app/ --cov=app                # with coverage
```

---

## Security & integrity

- **Confidentiality**: payloads AES-GCM encrypted with per-asset derived keys.
- **Non-repudiation**: Ed25519 signatures over payloads and evidence reports.
- **Tamper evidence**: hash-chained audit trail; `GET /api/v1/audit/verify` detects any change.
- **False-accusation defences** (doc §13.4): signature verification, chain-of-custody, registry resolution, independent verifier support.

---

## License

MIT — see [LICENSE.md](LICENSE.md). © 2024 Park Seong-Woo, AIMZ Media.
