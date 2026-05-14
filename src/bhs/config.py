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
