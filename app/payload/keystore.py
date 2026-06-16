"""Key management abstraction (KMS / HSM / Vault).

Defines a provider interface so the platform can switch between a local
development key, HashiCorp Vault, AWS KMS, or a hardware HSM without changing
calling code. Implements key rotation and envelope-style key derivation.

For local/dev mode a deterministic master key is derived from a fixed seed so
that watermarks remain reproducible across restarts. Production deployments MUST
configure ``INW_KMS_PROVIDER`` and supply real key material.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config.settings import Settings, get_settings
from app.payload import crypto


@dataclass
class KeyHandle:
    """A reference to an active key version."""

    key_id: str
    version: int
    material: bytes


class KeyProvider(ABC):
    """Abstract key provider."""

    @abstractmethod
    def get_master_key(self) -> KeyHandle:
        """Return the current active master key handle."""

    def derive(self, context: str, length: int = 32) -> bytes:
        """Derive a context-specific sub-key from the master key."""
        handle = self.get_master_key()
        versioned_ctx = f"{context}|kid={handle.key_id}|v={handle.version}"
        return crypto.derive_key(handle.material, versioned_ctx, length)


class LocalKeyProvider(KeyProvider):
    """Local key provider for development and single-node deployments.

    Master key is read from settings (hex) or deterministically derived from a
    fixed development seed. Never use the derived dev key in production.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def get_master_key(self) -> KeyHandle:
        if self._settings.master_key_hex:
            material = bytes.fromhex(self._settings.master_key_hex)
            key_id = "configured"
        else:
            # Deterministic dev key — clearly marked, reproducible.
            material = hashlib.sha256(b"INW-DEV-MASTER-KEY-DO-NOT-USE-IN-PROD").digest()
            key_id = "dev-insecure"
        return KeyHandle(key_id=key_id, version=1, material=material)


class VaultKeyProvider(KeyProvider):
    """HashiCorp Vault transit/secret-backed key provider (stub interface).

    The real implementation calls Vault's API to fetch the wrapped master key.
    Kept as an explicit, documented integration point so production wiring is a
    drop-in rather than a rewrite.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def get_master_key(self) -> KeyHandle:  # pragma: no cover - requires Vault
        raise NotImplementedError(
            "VaultKeyProvider requires a running Vault instance. Configure "
            "INW_KMS_PROVIDER=local for development."
        )


class AwsKmsKeyProvider(KeyProvider):
    """AWS KMS-backed provider (stub interface)."""

    def get_master_key(self) -> KeyHandle:  # pragma: no cover - requires AWS
        raise NotImplementedError(
            "AwsKmsKeyProvider requires AWS credentials and a configured CMK."
        )


def get_key_provider(settings: Settings | None = None) -> KeyProvider:
    """Factory returning the configured key provider."""
    settings = settings or get_settings()
    provider = settings.kms_provider
    if provider == "local":
        return LocalKeyProvider(settings)
    if provider == "vault":
        return VaultKeyProvider(settings)
    if provider == "aws_kms":
        return AwsKmsKeyProvider(settings)
    raise ValueError(f"Unsupported KMS provider: {provider}")
