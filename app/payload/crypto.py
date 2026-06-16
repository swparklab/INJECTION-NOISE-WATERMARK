"""Cryptographic primitives for the payload service.

Provides:
    - Key derivation (HKDF) from a master key with per-asset / per-key context
    - Deterministic keystream generation for spread-spectrum watermarking
    - Ed25519 digital signatures for non-repudiation / false-accusation defence
    - Key rotation metadata

In production the master key is supplied by an external KMS/HSM (see
:mod:`app.payload.keystore`). This module never persists raw key material.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def derive_key(master_key: bytes, context: str, length: int = 32) -> bytes:
    """Derive a sub-key from master key material using HKDF-SHA256.

    Args:
        master_key: High-entropy master key bytes (>= 16 bytes).
        context: Domain-separation string (e.g. ``"asset:ASSET-001:wm"``).
        length: Output key length in bytes.

    Returns:
        Derived key of ``length`` bytes.

    Raises:
        ValueError: If master key is too short.
    """
    if len(master_key) < 16:
        raise ValueError("master_key must be at least 16 bytes")
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=b"inw-watermark-hkdf-v1",
        info=context.encode("utf-8"),
    )
    return hkdf.derive(master_key)


def keystream(key: bytes, n: int) -> bytes:
    """Generate a deterministic pseudo-random keystream of ``n`` bytes.

    Uses HMAC-SHA256 in counter mode (a CSPRNG suitable for spread-spectrum
    chip sequences). Deterministic given the same key — required so the
    detector can regenerate the exact sequence used at embed time.

    Args:
        key: Secret key bytes.
        n: Number of output bytes.

    Returns:
        Keystream bytes of length ``n``.
    """
    out = bytearray()
    counter = 0
    while len(out) < n:
        block = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:n])


@dataclass
class SignatureKeyPair:
    """An Ed25519 keypair with serialisable raw bytes."""

    private_bytes: bytes
    public_bytes: bytes

    @classmethod
    def generate(cls) -> "SignatureKeyPair":
        """Generate a fresh Ed25519 keypair."""
        priv = Ed25519PrivateKey.generate()
        from cryptography.hazmat.primitives import serialization

        return cls(
            private_bytes=priv.private_bytes_raw(),
            public_bytes=priv.public_key().public_bytes_raw(),
        )

    @classmethod
    def from_master(cls, master_key: bytes, context: str = "signing:v1") -> "SignatureKeyPair":
        """Deterministically derive a signing keypair from the master key.

        This lets the platform reproduce its signing identity from KMS-held key
        material without separately storing the private signing key.
        """
        seed = derive_key(master_key, context, length=32)
        priv = Ed25519PrivateKey.from_private_bytes(seed)
        return cls(
            private_bytes=priv.private_bytes_raw(),
            public_bytes=priv.public_key().public_bytes_raw(),
        )


def sign(private_bytes: bytes, message: bytes) -> bytes:
    """Sign a message with an Ed25519 private key.

    Args:
        private_bytes: Raw 32-byte Ed25519 private key.
        message: Message to sign.

    Returns:
        64-byte signature.
    """
    priv = Ed25519PrivateKey.from_private_bytes(private_bytes)
    return priv.sign(message)


def verify(public_bytes: bytes, message: bytes, signature: bytes) -> bool:
    """Verify an Ed25519 signature.

    Args:
        public_bytes: Raw 32-byte Ed25519 public key.
        message: Message that was signed.
        signature: Signature to verify.

    Returns:
        True if the signature is valid, False otherwise.
    """
    from cryptography.exceptions import InvalidSignature

    pub = Ed25519PublicKey.from_public_bytes(public_bytes)
    try:
        pub.verify(signature, message)
        return True
    except InvalidSignature:
        return False
