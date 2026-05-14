from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

try:
    from minio import Minio
except ImportError:  # pragma: no cover
    Minio = None  # type: ignore


class ArtifactStore(ABC):
    """Artifact storage with URI convention: bhs://{run_id}/{name}"""

    @abstractmethod
    def put_bytes(self, run_id: str, name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        ...

    @abstractmethod
    def put_file(self, run_id: str, name: str, path: Path) -> str:
        ...


class LocalArtifactStore(ArtifactStore):
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str, name: str) -> Path:
        safe = name.replace("..", "_")
        p = self.base_dir / run_id / safe
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def put_bytes(self, run_id: str, name: str, data: bytes, content_type: str = "") -> str:
        p = self._path(run_id, name)
        p.write_bytes(data)
        return f"file://{p.resolve()}"

    def put_file(self, run_id: str, name: str, path: Path) -> str:
        data = Path(path).read_bytes()
        return self.put_bytes(run_id, name, data)


class MinIOArtifactStore(ArtifactStore):
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = False) -> None:
        if Minio is None:
            raise RuntimeError("minio package required")
        self._client = Minio(
            endpoint.replace("http://", "").replace("https://", ""),
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self.bucket = bucket
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)

    def put_bytes(self, run_id: str, name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        key = f"{run_id}/{name}"
        from io import BytesIO

        self._client.put_object(
            self.bucket,
            key,
            data=BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return f"s3://{self.bucket}/{key}"

    def put_file(self, run_id: str, name: str, path: Path) -> str:
        key = f"{run_id}/{name}"
        self._client.fput_object(self.bucket, key, str(path))
        return f"s3://{self.bucket}/{key}"


def build_artifact_store(
    *,
    local_dir: Path,
    minio_endpoint: str | None = None,
    minio_access_key: str | None = None,
    minio_secret_key: str | None = None,
    minio_bucket: str = "bhs-artifacts",
) -> ArtifactStore:
    if minio_endpoint and minio_access_key and minio_secret_key and Minio is not None:
        secure = minio_endpoint.startswith("https://")
        ep = minio_endpoint.replace("https://", "").replace("http://", "")
        return MinIOArtifactStore(ep, minio_access_key, minio_secret_key, minio_bucket, secure=secure)
    return LocalArtifactStore(local_dir)


def retention_sweep_local(base_dir: Path, keep_last_runs: int = 50) -> None:
    """Simple retention: keep newest run directories by mtime."""
    base = Path(base_dir)
    if not base.is_dir():
        return
    runs = sorted(
        [p for p in base.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for p in runs[keep_last_runs:]:
        import shutil

        shutil.rmtree(p, ignore_errors=True)


def fingerprint_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
