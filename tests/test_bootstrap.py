from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bhs.config import Settings
from bhs.dev_bootstrap import (
    compose_base,
    ensure_ollama,
    ensure_sandbox_image,
    run_compose,
    run_dev_bootstrap,
)
from bhs.paths import resolve_repo_root


def _touch_llm_compose(root: Path) -> None:
    d = root / "deploy"
    d.mkdir(parents=True, exist_ok=True)
    (d / "docker-compose.llm.yml").write_text(
        "services:\n  t:\n    image: alpine\n    command: [\"true\"]\n",
        encoding="utf-8",
    )


def test_resolve_repo_root_from_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _touch_llm_compose(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert resolve_repo_root() == tmp_path.resolve()


def test_resolve_repo_root_explicit(tmp_path: Path) -> None:
    _touch_llm_compose(tmp_path)
    assert resolve_repo_root(tmp_path) == tmp_path.resolve()


def test_resolve_repo_root_anchor_file(tmp_path: Path) -> None:
    _touch_llm_compose(tmp_path)
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)
    anchor = nested / "mod.py"
    anchor.write_text("#", encoding="utf-8")
    assert resolve_repo_root(anchor_file=anchor) == tmp_path.resolve()


def test_resolve_repo_root_missing() -> None:
    assert resolve_repo_root(Path("/nonexistent/no-such-bhs-root-xyz")) is None


def test_compose_base_respects_podman(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BHS_CONTAINER_RUNTIME", "podman")
    assert compose_base() == ["podman", "compose"]
    monkeypatch.delenv("BHS_CONTAINER_RUNTIME", raising=False)
    assert compose_base()[0] == "docker"


def test_run_compose_builds_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _touch_llm_compose(tmp_path)
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("bhs.dev_bootstrap.subprocess.run", fake_run)
    run_compose(tmp_path, Path("deploy") / "docker-compose.llm.yml", ["config"])
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert "compose" in cmd
    assert any("docker-compose.llm.yml" in str(x) for x in cmd)
    assert captured["cwd"] == tmp_path


def test_run_compose_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _touch_llm_compose(tmp_path)

    def fake_run(*a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["x"], 1, "", "boom")

    monkeypatch.setattr("bhs.dev_bootstrap.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="compose failed"):
        run_compose(tmp_path, Path("deploy") / "docker-compose.llm.yml", ["up", "-d"])


def test_ensure_ollama_disabled() -> None:
    s = Settings(ollama_enabled=False)
    ensure_ollama(s, Path("."))  # no-op


def test_ensure_ollama_skip_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        "bhs.dev_bootstrap._ollama_tags",
        lambda *a, **k: called.append("tags") or {"models": []},
    )
    s = Settings(ollama_enabled=True, skip_auto_ollama=True)
    ensure_ollama(s, Path("."))
    assert not called


def test_ensure_ollama_model_already_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "bhs.dev_bootstrap._ollama_tags",
        lambda base, timeout=5.0: {"models": [{"name": "gemma3:1b"}]},
    )
    pull = MagicMock()
    monkeypatch.setattr("bhs.dev_bootstrap._pull_model", pull)
    compose = MagicMock()
    monkeypatch.setattr("bhs.dev_bootstrap._compose_up_llm", compose)
    s = Settings(ollama_enabled=True, ollama_model="gemma3:1b")
    ensure_ollama(s, Path("."))
    pull.assert_not_called()
    compose.assert_not_called()


def test_ensure_ollama_unreachable_no_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bhs.dev_bootstrap._ollama_tags", lambda base, timeout=5.0: None)
    s = Settings(ollama_enabled=True)
    with pytest.raises(SystemExit):
        ensure_ollama(s, None)


def test_ensure_ollama_compose_and_pull(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = {"n": 0}

    def fake_tags(base: str, timeout: float = 5.0) -> dict | None:
        state["n"] += 1
        if state["n"] == 1:
            return None
        return {"models": []}

    monkeypatch.setattr("bhs.dev_bootstrap._ollama_tags", fake_tags)
    compose = MagicMock()
    monkeypatch.setattr("bhs.dev_bootstrap._compose_up_llm", compose)
    pull = MagicMock()
    monkeypatch.setattr("bhs.dev_bootstrap._pull_model", pull)
    s = Settings(ollama_enabled=True, ollama_model="m1")
    ensure_ollama(s, tmp_path)
    compose.assert_called_once_with(tmp_path)
    pull.assert_called_once()


def test_ensure_sandbox_image_skips_when_exists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("bhs.dev_bootstrap._image_exists", lambda img: True)
    run = MagicMock()
    monkeypatch.setattr("bhs.dev_bootstrap.subprocess.run", run)
    ensure_sandbox_image("bughunter-sandbox:local", tmp_path)
    run.assert_not_called()


def test_run_dev_bootstrap_observability_requires_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bhs.dev_bootstrap.resolve_repo_root", lambda *a, **k: None)
    s = Settings(auto_observability=True)
    with pytest.raises(SystemExit):
        run_dev_bootstrap(s)


def test_run_dev_bootstrap_sandbox_requires_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BHS_SANDBOX_MODE", "docker")
    monkeypatch.setattr("bhs.dev_bootstrap.resolve_repo_root", lambda *a, **k: None)
    s = Settings(auto_sandbox_image=True)
    with pytest.raises(SystemExit):
        run_dev_bootstrap(s)
    monkeypatch.delenv("BHS_SANDBOX_MODE", raising=False)
