# Architecture

This document describes the components of the INJECTION-NOISE-WATERMARK platform
and how data flows through the embed, detect, trace, remove, and verify paths.

## Design principle: token + registry

The watermark channel is low-capacity and lossy (re-encoding, scaling, partial
crops). Embedding a full provenance record directly would be fragile. Instead:

1. The watermark carries a **small ECC-protected token** (a few bytes).
2. The **registry** stores the full delivery record (asset, client, delivery,
   recipient, distribution, lineage) keyed by that token.
3. On trace, the recovered token is resolved through the registry to the
   recipient and chain-of-custody.

This keeps the embedded bitstream tiny (so it survives aggressive recompression)
while the rich metadata lives safely server-side.

## Components

### Payload (`app/payload`)
- `crypto.py` — HKDF key derivation, HMAC-counter keystream (for spread-spectrum
  chip sequences), Ed25519 sign/verify.
- `keystore.py` — `KeyProvider` abstraction (`local`, `vault`, `aws_kms`, `hsm`)
  with rotation-aware, versioned key derivation.
- `service.py`
  - `PayloadService` — full self-contained payload: AES-GCM + length-prefixed
    body + Ed25519 signature, all wrapped in Reed-Solomon ECC.
  - `TokenCodec` — compact `[token id][CRC16]` framed in Reed-Solomon ECC; this
    is what the watermark actually carries.

### Core engines (`app/core`)
- `base.py` — `WatermarkEngine` interface (`embed`, `detect`, `capacity_bits`)
  with `EmbedResult` / `DetectResult`.
- `frequency_watermark.py` — block-DCT spread spectrum in mid-frequency
  coefficients, optional DWT carrier, perceptual masking, keyed PN signs.
- `keyed_gaussian.py` — global-DCT mid-band Gaussian spread spectrum; the
  primary `custom-noise` engine. Supports multi-key overlay and anti-collusion.
- `registry.py` — engine **model selector**: maps a model id to an engine
  instance; registers built-in engines and adapters.
- `detection_engine.py` — blind detection orchestration: per-image detection,
  blind multi-model search, and video majority frame-vote; recovers the token
  via ECC, derives a z-score confidence.
- `watermark_engine.py` — `WatermarkService` façade tying payload/token + key
  provider + selected engine together for the API.
- `tracking_engine.py` — leak tracing: detect → token → registry lookup →
  recipient + lineage graph; persists a `WatermarkTrace`.
- `removal_engine.py` — five removal/forensic methods.

### Adapters (`app/adapters`)
- `base.py` — `AdapterEngine`: prefer a native neural backend, transparently
  fall back to the internal engine (flagged in result metadata).
- `neural_adapters.py` — VideoSeal, Meta Seal, InvisMark, WAM.
- `diffusion_adapters.py` — Tree-Ring, Gaussian Shading, RingID (wrap the
  original `src/tree_ring_watermark` research code).

### Provenance (`app/provenance`)
- `registry.py` — assets, deliveries, payload-fingerprint lookup, lineage walk.
- `audit.py` — hash-chained, append-only audit log with `verify_chain()` and a
  monotonic `seq` for stable ordering.
- `c2pa.py` — build/verify signed C2PA-style content-credential manifests
  (native `c2pa` if installed, else signed JSON sidecar).

### Evidence (`app/reports`)
- `evidence.py` — generate signed forensic/legal/audit reports from a trace,
  including an audit-chain integrity statement; independently verifiable.

### Persistence (`app/db`)
- `base.py` — engine/session, `init_db`, `session_scope`.
- `models.py` — `watermark_models`, `assets`, `deliveries`, `watermark_traces`,
  `watermark_removals`, `audit_logs`, `provenance_records`, `evidence_reports`.

### API (`app/api`) + `app/main.py`
FastAPI routers wired under `/api/v1`. `main.py` initialises the DB, registers
engines, and seeds the model table at startup.

## Data flows

### Embed
```
image + metadata
  → WatermarkService.embed_image
      → TokenCodec.new_token_id + encode (ECC)
      → key = KeyProvider.derive("watermark:<asset>")
      → engine.embed(image, wire, key, strength)
  → RegistryService.record_delivery(token fingerprint, recipient, lineage parent)
  → C2PAService.build_manifest (signed) + sidecar
  → AuditService.log("embed.create")
  → store watermarked PNG
```

### Trace
```
suspect file (possibly re-encoded)
  → TrackingEngine.trace_image
      → candidate assets from registry (optionally per client)
      → DetectionEngine blind detect → token (ECC + CRC)
      → RegistryService.find_delivery_by_fingerprint(token)
      → RegistryService.lineage(delivery) → [MASTER, …, delivery]
  → persist WatermarkTrace + AuditService.log("trace.run")
  → (optional) EvidenceService.generate → signed report
```

### Detection confidence
Both engines compute a per-bit correlation z-score against an estimated host
noise scale. `mean(|z|)` is ~0.8 under the null (wrong/no key) and large under a
true mark, giving clean separation. A CRC-valid token recovery overrides raw
confidence to ~0.9, since exact recovery is decisive.

## Robustness strategy
- **ECC**: Reed-Solomon over the token tolerates residual bit errors from lossy
  channels.
- **Spread spectrum**: each bit spread over hundreds of coefficients → high
  processing gain, low per-coefficient amplitude (imperceptible, hard to remove).
- **Mid-frequency band**: survives JPEG/H.264 quantisation while staying out of
  the visually sensitive low band.
- **Frame voting**: video aggregates per-frame token recoveries by majority,
  surviving per-frame noise and partial corruption.

## Production notes
- Swap `INW_KMS_PROVIDER` to `vault`/`aws_kms`/`hsm` and supply real key material.
- Point `INW_REGISTRY_DB_URL` at PostgreSQL; run Alembic migrations.
- Put object storage (S3/MinIO) behind `INW_S3_*`; offload heavy embed/detect to
  Celery workers; expose Prometheus metrics.
