from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BHS_", extra="ignore")

    sqlite_path: Path = Field(default=Path(".bhs/state.sqlite"))
    redis_url: str | None = None
    minio_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_bucket: str = "bhs-artifacts"
    artifact_local_dir: Path = Field(default=Path(".bhs/artifacts"))
    otel_exporter_otlp_endpoint: str | None = None
    github_token: str | None = None
    github_repo: str | None = None  # owner/name

    max_iterations: int = Field(default=1, ge=1, le=50)
    sandbox_cpu_cores: float | None = Field(default=None, description="Optional CPU cap for Docker/Podman sandbox")

    ollama_enabled: bool = False
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma3:1b"
    ollama_timeout_sec: float = Field(default=120.0, ge=5.0, le=600.0)
