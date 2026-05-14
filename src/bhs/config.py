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

    repo_path: Path | None = Field(
        default=None,
        description="Path to the repository under analysis; env BHS_REPO_PATH (CLI --repo overrides)",
    )

    max_iterations: int = Field(default=1, ge=1, le=5000)
    stop_bug_count: int = Field(
        default=0,
        ge=0,
        le=1000,
        description="After dedupe in bug_logger: if >0 and count >= this, finalize early (0=disabled)",
    )
    sandbox_cpu_budget_seconds: float | None = Field(
        default=None,
        ge=30.0,
        description="Sandbox CPU quota (compileall cumulative); if unset, scales with max_iterations",
    )
    sandbox_cpu_cores: float | None = Field(default=None, description="Optional CPU cap for Docker/Podman sandbox")

    project_root: Path | None = Field(
        default=None,
        description="Explicit repo root for bootstrap (compose paths); env BHS_PROJECT_ROOT",
    )

    auto_observability: bool = Field(
        default=False,
        description="Run docker compose for observability stack before bhs-run",
    )
    auto_sandbox_image: bool = Field(
        default=False,
        description="Build sandbox image if missing (non-local sandbox only)",
    )
    skip_auto_ollama: bool = Field(
        default=False,
        description="Do not start compose / pull model when ollama_enabled",
    )

    ollama_enabled: bool = False
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma3:1b"
    ollama_timeout_sec: float = Field(default=120.0, ge=5.0, le=600.0)
    ollama_pull_timeout_sec: float = Field(
        default=3600.0,
        ge=60.0,
        le=86400.0,
        description="Timeout for streaming /api/pull during bootstrap",
    )

    def resolved_sandbox_cpu_seconds(self) -> float:
        """CPU budget for check_quotas; defaults to max(120, 3s per configured iteration)."""
        if self.sandbox_cpu_budget_seconds is not None:
            return float(self.sandbox_cpu_budget_seconds)
        return max(120.0, float(self.max_iterations) * 3.0)
