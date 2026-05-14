from __future__ import annotations

from pathlib import Path

import pytest

from bhs.cli import resolve_run_repo
from bhs.config import Settings


def test_resolve_run_repo_cli_wins(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    s = Settings(repo_path=b)
    assert resolve_run_repo(a, s) == a.resolve()


def test_resolve_run_repo_from_settings(tmp_path: Path) -> None:
    target = tmp_path / "proj"
    target.mkdir()
    s = Settings(repo_path=target)
    assert resolve_run_repo(None, s) == target.resolve()


def test_resolve_run_repo_default_dot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    s = Settings()
    assert resolve_run_repo(None, s) == tmp_path.resolve()
