"""Idempotent dev stack bootstrap before bhs-run (Ollama, sandbox image, observability)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from bhs.config import Settings
from bhs.paths import resolve_repo_root


def _use_podman() -> bool:
    return os.environ.get("BHS_CONTAINER_RUNTIME", "").lower() == "podman"


def compose_base() -> list[str]:
    return ["podman", "compose"] if _use_podman() else ["docker", "compose"]


def run_compose(
    repo_root: Path,
    compose_relative: Path,
    extra: list[str],
) -> None:
    """Run ``docker compose`` / ``podman compose`` with project directory next to the compose file."""
    compose_abs = (repo_root / compose_relative).resolve()
    if not compose_abs.is_file():
        raise FileNotFoundError(f"Compose file not found: {compose_abs}")
    project_dir = compose_abs.parent
    cmd = [
        *compose_base(),
        "-f",
        str(compose_abs),
        "--project-directory",
        str(project_dir),
        *extra,
    ]
    r = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip()
        raise RuntimeError(f"compose failed (exit {r.returncode}): {msg or cmd}")


def ensure_observability(repo_root: Path) -> None:
    run_compose(
        repo_root,
        Path("deploy") / "docker-compose.observability.yml",
        ["up", "-d"],
    )


def _ollama_tags(base: str, *, timeout: float) -> dict[str, Any] | None:
    url = base.rstrip("/") + "/api/tags"
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(url)
            if r.status_code == 200:
                return r.json()
    except Exception:
        return None
    return None


def _model_in_tags(data: dict[str, Any], model: str) -> bool:
    for m in data.get("models") or []:
        if isinstance(m, dict) and m.get("name") == model:
            return True
    return False


def _wait_ollama(base: str, *, attempts: int = 45, delay_sec: float = 2.0) -> dict[str, Any]:
    for _ in range(attempts):
        data = _ollama_tags(base, timeout=3.0)
        if data is not None:
            return data
        time.sleep(delay_sec)
    raise RuntimeError(
        f"Ollama API at {base} did not become reachable after "
        f"{attempts * delay_sec:.0f}s (check Docker/Podman and compose logs)."
    )


def _compose_up_llm(repo_root: Path) -> None:
    run_compose(repo_root, Path("deploy") / "docker-compose.llm.yml", ["up", "-d"])


def _pull_model(base: str, model: str, timeout_sec: float) -> None:
    url = base.rstrip("/") + "/api/pull"
    with httpx.Client(timeout=timeout_sec) as client:
        with client.stream("POST", url, json={"name": model}) as resp:
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Ollama pull failed: {e.response.text}") from e
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                status = chunk.get("status")
                if isinstance(status, str) and status:
                    print(f"[ollama pull] {status}", file=sys.stderr)


def ensure_ollama(settings: Settings, repo_root: Path | None) -> None:
    if not settings.ollama_enabled or settings.skip_auto_ollama:
        return

    base = settings.ollama_base_url.rstrip("/")
    tags = _ollama_tags(base, timeout=5.0)

    if tags is None:
        if repo_root is None:
            print(
                "BHS_OLLAMA_ENABLED=true but Ollama is not reachable and repo root is unknown. "
                "Start Ollama manually or set BHS_PROJECT_ROOT to the BugHunter Swarm checkout "
                "(directory containing deploy/docker-compose.llm.yml).",
                file=sys.stderr,
            )
            raise SystemExit(1)
        print("Starting Ollama via compose (deploy/docker-compose.llm.yml)...", file=sys.stderr)
        _compose_up_llm(repo_root)
        tags = _wait_ollama(base)

    if _model_in_tags(tags, settings.ollama_model):
        return

    print(
        f"Pulling Ollama model {settings.ollama_model!r} (this may take a while)...",
        file=sys.stderr,
    )
    _pull_model(base, settings.ollama_model, float(settings.ollama_pull_timeout_sec))


def _image_exists(image: str) -> bool:
    if _use_podman():
        r = subprocess.run(
            ["podman", "image", "exists", image],
            capture_output=True,
            text=True,
            check=False,
        )
        return r.returncode == 0
    r = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.returncode == 0


def ensure_sandbox_image(image: str, repo_root: Path) -> None:
    if _image_exists(image):
        return
    dockerfile = repo_root / "docker" / "sandbox" / "Dockerfile"
    if not dockerfile.is_file():
        raise FileNotFoundError(f"Sandbox Dockerfile not found: {dockerfile}")
    runtime = "podman" if _use_podman() else "docker"
    print(f"Building sandbox image {image!r} ({runtime} build)...", file=sys.stderr)
    subprocess.run(
        [
            runtime,
            "build",
            "-t",
            image,
            "-f",
            str(dockerfile),
            str(repo_root),
        ],
        cwd=repo_root,
        check=True,
    )


def run_dev_bootstrap(settings: Settings) -> None:
    anchor = Path(__file__).resolve()
    repo_root = resolve_repo_root(settings.project_root, anchor_file=anchor)

    if settings.auto_observability:
        if repo_root is None:
            print(
                "BHS_AUTO_OBSERVABILITY=true but project root not found; "
                "set BHS_PROJECT_ROOT or run from the repository checkout.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        try:
            ensure_observability(repo_root)
        except (RuntimeError, FileNotFoundError) as e:
            print(f"Observability bootstrap failed: {e}", file=sys.stderr)
            raise SystemExit(1) from e

    if settings.ollama_enabled and not settings.skip_auto_ollama:
        try:
            ensure_ollama(settings, repo_root)
        except RuntimeError as e:
            print(f"Ollama bootstrap failed: {e}", file=sys.stderr)
            raise SystemExit(1) from e

    if settings.auto_sandbox_image and os.environ.get("BHS_SANDBOX_MODE", "").lower() != "local":
        if repo_root is None:
            print(
                "BHS_AUTO_SANDBOX_IMAGE=true but project root not found; "
                "set BHS_PROJECT_ROOT or run from the repository checkout.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        image = os.environ.get("BHS_SANDBOX_IMAGE", "bughunter-sandbox:local")
        try:
            ensure_sandbox_image(image, repo_root)
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"Sandbox image bootstrap failed: {e}", file=sys.stderr)
            raise SystemExit(1) from e
