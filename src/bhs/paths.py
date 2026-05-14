"""Resolve repository root for bootstrap (compose files, Dockerfile)."""

from __future__ import annotations

import os
from pathlib import Path

_LLM_COMPOSE_REL = Path("deploy") / "docker-compose.llm.yml"


def resolve_repo_root(
    explicit: Path | str | None = None,
    *,
    anchor_file: Path | None = None,
) -> Path | None:
    """
    Find project root containing deploy/docker-compose.llm.yml.

    Order:
    1. ``explicit`` argument
    2. env ``BHS_PROJECT_ROOT``
    3. Parents of ``anchor_file`` (e.g. ``__file__`` of ``dev_bootstrap``) — editable / tests
    4. Parents of ``Path.cwd()``
    """
    if explicit is not None:
        p = Path(explicit).expanduser().resolve()
        return p if _has_llm_compose(p) else None

    env_root = os.environ.get("BHS_PROJECT_ROOT", "").strip()
    if env_root:
        p = Path(env_root).expanduser().resolve()
        return p if _has_llm_compose(p) else None

    if anchor_file is not None:
        start = Path(anchor_file).resolve().parent
        for d in [start, *start.parents]:
            if _has_llm_compose(d):
                return d

    for base in (Path.cwd().resolve(),):
        for d in [base, *base.parents]:
            if _has_llm_compose(d):
                return d

    return None


def _has_llm_compose(root: Path) -> bool:
    return (root / _LLM_COMPOSE_REL).is_file()
