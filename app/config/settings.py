"""Centralized application settings.

Loads configuration from environment variables with sensible defaults so the
platform runs out-of-the-box for local development while remaining fully
configurable for production (KMS-backed keys, PostgreSQL, S3, Redis, etc.).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings resolved from environment / .env file."""

    model_config = SettingsConfigDict(
        env_prefix="INW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General ---
    app_name: str = "Injection Noise Watermark Platform"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # --- Storage paths (local fallback when object storage not configured) ---
    data_dir: Path = Field(default=Path("./_data"))
    registry_db_url: str = "sqlite:///./_data/registry.db"

    # --- Object storage (S3 / MinIO) ---
    s3_endpoint_url: str | None = None
    s3_bucket: str = "inw-assets"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"

    # --- Cache / queue ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Cryptography ---
    # Master key material. In production this is supplied by Vault / KMS / HSM.
    # For local dev a deterministic dev key is derived if none is provided.
    master_key_hex: str | None = None
    key_rotation_days: int = 90
    kms_provider: Literal["local", "vault", "aws_kms", "hsm"] = "local"

    # --- Payload / ECC ---
    ecc_redundancy_bytes: int = 32  # Reed-Solomon parity symbols
    payload_version: int = 1

    # --- Watermark defaults ---
    default_model: str = "custom-noise"
    default_strength: float = 0.12

    # --- Detection ---
    detection_confidence_threshold: float = 0.5
    frame_vote_threshold: float = 0.5

    # --- Observability ---
    log_level: str = "INFO"
    enable_metrics: bool = True

    def ensure_dirs(self) -> None:
        """Create local data directories if they do not exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "assets").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "evidence").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return cached singleton settings instance."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
