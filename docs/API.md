# API Reference

Base URL: `/api/v1` · Interactive docs: `/docs` (Swagger) · `/redoc`

All media endpoints accept `multipart/form-data` with a `file` field plus form
fields. Responses are JSON.

---

## Health

### `GET /health`
Liveness probe.
```json
{ "status": "ok", "models": ["custom-noise", "frequency", ...] }
```

### `GET /`
Service info (name, version, docs link).

---

## Models

### `GET /api/v1/models` · `POST /api/v1/watermark/models`
List available watermark models and capabilities.
```json
{
  "models": ["custom-noise", "frequency", "videoseal", ...],
  "details": [{ "id": "custom-noise", "name": "Custom Noise Engine",
               "media_types": ["image","video"], "description": "..." }]
}
```

---

## Embed

### `POST /api/v1/embed`
Embed a watermark into an image and register the delivery.

| field | type | required | default | description |
|---|---|---|---|---|
| `file` | file | ✓ | — | source image |
| `asset_id` | str | ✓ | — | master work id |
| `client_id` | str | ✓ | — | owning client/tenant |
| `recipient_id` | str | ✓ | — | recipient (leak attribution) |
| `delivery_id` | str | | auto uuid | delivery id |
| `model` | str | | `custom-noise` | watermark model |
| `strength` | float | | `0.18` | embedding strength |
| `distribution_id` | str | | `""` | distribution channel |
| `parent_delivery_id` | str | | — | lineage parent |
| `title` | str | | `""` | asset title |

```json
{
  "delivery_id": "…", "asset_id": "ASSET-001", "token_id": "71d5616aaa08",
  "model": "custom-noise", "psnr": 47.88, "ssim": 0.9904,
  "output_uri": "_data/assets/….png", "c2pa_manifest_uri": "_data/assets/….c2pa.json"
}
```

---

## Detect

### `POST /api/v1/detect`
Detect a watermark in an image for a known asset + model.

| field | required | default |
|---|---|---|
| `file` | ✓ | — |
| `asset_id` | ✓ | — |
| `model` | | `custom-noise` |

```json
{ "detected": true, "confidence": 0.9, "token_id": "71d5616aaa08",
  "crc_ok": true, "model": "custom-noise" }
```

### `POST /api/v1/video/detect`
Same fields plus `max_frames` (default 16). Detects across sampled frames by
majority vote.

---

## Trace

### `POST /api/v1/trace`
Resolve a suspect image to its originating delivery / recipient.

| field | required | default | description |
|---|---|---|---|
| `file` | ✓ | — | suspect image |
| `client_id` | | — | restrict candidate assets (faster, fewer FPs) |
| `model` | | all | restrict to a known model |

```json
{
  "found": true, "asset_id": "ASSET-001", "delivery_id": "…",
  "recipient": "studio@partner.com", "client_id": "CLIENT-A",
  "watermark_model": "custom-noise", "confidence": 0.9,
  "signature_valid": true, "trace_path": ["MASTER", "DELIVERY-…"],
  "detail": { "token": "…", "trace_id": "…" }
}
```

### `POST /api/v1/video/trace`
Same plus `model` (default `custom-noise`) and `max_frames`.

---

## Remove (rights-holder)

### `POST /api/v1/remove`
Remove or forensically isolate a watermark. All removals are audit-logged.

| field | required | default | description |
|---|---|---|---|
| `file` | ✓ | — | watermarked image |
| `method` | | `frequency_suppression` | see below |
| `asset_id` | | — | required for `template_cancellation` |
| `model` | | `custom-noise` | |
| `requested_by` | | `""` | actor for audit |

Methods: `frequency_suppression`, `neural_denoising`, `template_cancellation`
(keyed), `residual_reconstruction`, `watermark_isolation`.

```json
{ "method": "frequency_suppression", "watermark_detected": true,
  "removal_success": 0.91, "quality_score": 0.97, "output_uri": "_data/assets/….png" }
```

---

## Provenance & Evidence

### `POST /api/v1/provenance/verify`
Body: a C2PA manifest JSON object. Verifies its signature.
```json
{ "valid": true, "asset_id": "ASSET-001", "watermark_model": "custom-noise",
  "detail": { "delivery_id": "…", "recipient": "…" } }
```

### `POST /api/v1/evidence/generate?trace_id=…&report_type=forensic`
Generate a signed evidence report from a stored trace id.
```json
{ "report_type": "forensic", "generated_at": "…", "signature": "…",
  "public_key": "…", "audit_chain_valid": true,
  "statements": ["A watermark … recovered with confidence 90% …", "…"],
  "trace": { … } }
```

---

## Audit

### `GET /api/v1/audit/verify`
Verify the integrity of the append-only audit chain.
```json
{ "valid": true, "entries": 42 }
```

### `GET /api/v1/audit/logs?limit=100`
List recent audit entries.

---

## Errors
- `400` — bad/undecodable media, payload exceeds capacity, unknown model/method.
- `404` — unknown trace id (evidence generation).
