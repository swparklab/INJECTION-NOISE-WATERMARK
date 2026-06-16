"""Payload service: structured, encrypted, error-corrected, signed payloads.

A watermark payload carries the identifiers needed to trace a leak back to a
specific delivery and recipient. The on-the-wire payload layout is::

    +---------+-----------+----------------------+-----------+
    | header  |  ciphertext (AES-GCM)           | RS parity |
    +---------+-----------+----------------------+-----------+
    | 1B ver  | 12B nonce | N bytes              | M bytes   |

The plaintext (before encryption) is a compact, length-prefixed record of the
identifier fields plus an Ed25519 signature over the canonical field bytes.

Design goals:
    - **Confidentiality**: payload contents are AES-GCM encrypted.
    - **Integrity / non-repudiation**: Ed25519 signature embedded.
    - **Robustness**: Reed-Solomon ECC tolerates partial corruption from
      lossy channels (JPEG, re-encoding, partial detection).
    - **Versioning + key rotation**: header carries version; keys derived via
      :mod:`app.payload.keystore` with rotation-aware context.
"""

from __future__ import annotations

import json
import os
import struct
from dataclasses import asdict, dataclass, field

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from reedsolo import RSCodec, ReedSolomonError

from app.config.settings import get_settings
from app.payload import crypto
from app.payload.keystore import KeyProvider, get_key_provider

_MAGIC_VERSION = 1
_NONCE_LEN = 12


@dataclass
class WatermarkPayload:
    """Logical payload describing the provenance of a delivered asset.

    Attributes:
        asset_id: Master work identifier.
        client_id: Owning client / tenant.
        delivery_id: Specific delivery instance.
        recipient_id: Recipient the copy was issued to (leak attribution).
        watermark_model: Model identifier used to embed (for trace decoding).
        distribution_id: Global distribution channel identifier.
        version: Payload schema version.
        extra: Arbitrary additional key/value metadata.
    """

    asset_id: str
    client_id: str
    delivery_id: str
    recipient_id: str
    watermark_model: str = "custom-noise"
    distribution_id: str = ""
    version: int = _MAGIC_VERSION
    extra: dict[str, str] = field(default_factory=dict)

    def canonical_bytes(self) -> bytes:
        """Return deterministic canonical byte encoding (for signing)."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")


class PayloadService:
    """Encode and decode watermark payloads with ECC + crypto + signature."""

    def __init__(
        self,
        key_provider: KeyProvider | None = None,
        ecc_bytes: int | None = None,
    ) -> None:
        """Initialise the payload service.

        Args:
            key_provider: Key provider (defaults to configured provider).
            ecc_bytes: Reed-Solomon parity symbol count (defaults from settings).
        """
        settings = get_settings()
        self.key_provider = key_provider or get_key_provider(settings)
        self.ecc_bytes = ecc_bytes if ecc_bytes is not None else settings.ecc_redundancy_bytes
        self._rs = RSCodec(self.ecc_bytes)

    # -- key helpers -------------------------------------------------------
    def _enc_key(self, asset_id: str) -> bytes:
        return self.key_provider.derive(f"payload:enc:{asset_id}", length=32)

    def _signing_keypair(self) -> crypto.SignatureKeyPair:
        handle = self.key_provider.get_master_key()
        return crypto.SignatureKeyPair.from_master(handle.material, "payload:sign:v1")

    @property
    def public_key(self) -> bytes:
        """Public signing key for independent third-party verification."""
        return self._signing_keypair().public_bytes

    # -- encode ------------------------------------------------------------
    def encode(self, payload: WatermarkPayload) -> bytes:
        """Serialise, sign, encrypt and ECC-protect a payload.

        Args:
            payload: Logical payload to encode.

        Returns:
            Opaque payload bytes ready to be embedded by a watermark engine.
        """
        body = payload.canonical_bytes()
        keypair = self._signing_keypair()
        signature = crypto.sign(keypair.private_bytes, body)

        # plaintext = len-prefixed body + signature
        plaintext = struct.pack(">I", len(body)) + body + signature

        enc_key = self._enc_key(payload.asset_id)
        nonce = os.urandom(_NONCE_LEN)
        ciphertext = AESGCM(enc_key).encrypt(nonce, plaintext, None)

        header = struct.pack(">B", _MAGIC_VERSION)
        framed = header + nonce + ciphertext
        # Reed-Solomon over the whole frame for channel robustness.
        return bytes(self._rs.encode(framed))

    # -- decode ------------------------------------------------------------
    def decode(self, raw: bytes, asset_id_hint: str | None = None) -> tuple[WatermarkPayload, bool]:
        """Decode ECC-protected payload bytes back into a payload.

        Args:
            raw: Bytes recovered from a watermark detector (may be noisy).
            asset_id_hint: Optional asset id to derive the decryption key when
                the payload itself is needed to learn the asset id. If omitted,
                the asset id is recovered after a first decrypt attempt using a
                registry-assisted flow (see :meth:`decode_with_keys`).

        Returns:
            Tuple of ``(payload, signature_valid)``.

        Raises:
            ValueError: If ECC correction or decryption irrecoverably fails.
        """
        try:
            framed = bytes(self._rs.decode(raw)[0])
        except ReedSolomonError as exc:  # pragma: no cover - corruption path
            raise ValueError(f"ECC decode failed: {exc}") from exc

        if not framed or framed[0] != _MAGIC_VERSION:
            raise ValueError("Unsupported or corrupt payload header")

        nonce = framed[1 : 1 + _NONCE_LEN]
        ciphertext = framed[1 + _NONCE_LEN :]

        # The encryption key is asset-scoped. When the asset id is unknown we
        # rely on a hint (registry lookup supplies candidate asset ids).
        if asset_id_hint is None:
            raise ValueError(
                "asset_id_hint required to derive decryption key; use "
                "decode_with_keys() for registry-assisted recovery"
            )

        enc_key = self._enc_key(asset_id_hint)
        try:
            plaintext = AESGCM(enc_key).decrypt(nonce, ciphertext, None)
        except Exception as exc:  # noqa: BLE001 - AEAD failure
            raise ValueError("Payload decryption/authentication failed") from exc

        (body_len,) = struct.unpack(">I", plaintext[:4])
        body = plaintext[4 : 4 + body_len]
        signature = plaintext[4 + body_len :]

        data = json.loads(body.decode("utf-8"))
        payload = WatermarkPayload(**data)

        keypair = self._signing_keypair()
        sig_valid = crypto.verify(keypair.public_bytes, body, signature)
        return payload, sig_valid

    def decode_with_keys(
        self, raw: bytes, candidate_asset_ids: list[str]
    ) -> tuple[WatermarkPayload, bool] | None:
        """Attempt decode against a set of candidate asset ids from the registry.

        Args:
            raw: Recovered payload bytes.
            candidate_asset_ids: Asset ids to try (e.g. from a registry scan).

        Returns:
            ``(payload, signature_valid)`` for the first candidate that decrypts
            and authenticates, or ``None`` if none match.
        """
        for asset_id in candidate_asset_ids:
            try:
                return self.decode(raw, asset_id_hint=asset_id)
            except ValueError:
                continue
        return None

    # -- capacity ----------------------------------------------------------
    def overhead_bytes(self) -> int:
        """Return fixed framing overhead (header + nonce + ECC parity)."""
        return 1 + _NONCE_LEN + self.ecc_bytes + 16  # +16 AES-GCM tag


class TokenCodec:
    """Compact, ECC-protected delivery token for low-capacity watermarks.

    The full :class:`WatermarkPayload` (asset/client/delivery/recipient + crypto)
    is stored in the registry. The *watermark itself* only needs to carry a small
    opaque token that the registry resolves back to the full delivery during a
    trace. This keeps the embedded bitstream tiny so it survives aggressive
    re-encoding while ECC corrects residual bit errors.

    Layout (before ECC):  ``[8-byte token id][2-byte CRC16]``
    Layout (wire):        ``RS(token id + crc, parity)``
    """

    def __init__(self, token_bytes: int = 6, parity_bytes: int = 10) -> None:
        """Initialise the token codec.

        Args:
            token_bytes: Length of the random token id.
            parity_bytes: Reed-Solomon parity symbols (error correction power).
        """
        self.token_bytes = token_bytes
        self.parity_bytes = parity_bytes
        self._rs = RSCodec(parity_bytes)

    def new_token_id(self, n: int | None = None) -> bytes:
        """Generate a fresh random token id of the configured length."""
        return os.urandom(n if n is not None else self.token_bytes)

    @staticmethod
    def _crc16(data: bytes) -> int:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
        return crc

    def encode(self, token_id: bytes) -> bytes:
        """ECC-encode a token id into wire bytes for embedding."""
        if len(token_id) != self.token_bytes:
            raise ValueError(f"token_id must be {self.token_bytes} bytes")
        crc = self._crc16(token_id)
        framed = token_id + crc.to_bytes(2, "big")
        return bytes(self._rs.encode(framed))

    def decode(self, raw: bytes) -> tuple[bytes, bool]:
        """ECC-decode wire bytes back to a token id.

        Returns:
            Tuple ``(token_id, crc_ok)``. ``crc_ok`` indicates the CRC matched
            after ECC correction (high-confidence recovery).
        """
        try:
            framed = bytes(self._rs.decode(raw)[0])
        except ReedSolomonError:
            return b"", False
        token_id = framed[: self.token_bytes]
        crc_stored = int.from_bytes(framed[self.token_bytes : self.token_bytes + 2], "big")
        crc_ok = self._crc16(token_id) == crc_stored
        return token_id, crc_ok

    def wire_len(self) -> int:
        """Length in bytes of the ECC-encoded token on the wire."""
        return self.token_bytes + 2 + self.parity_bytes
