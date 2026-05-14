from __future__ import annotations

from typing import Any

from bhs.persistence.sqlite_store import state_fingerprint
from bhs.persistence.sqlite_store import SqliteRunStore


_store: SqliteRunStore | None = None


def set_audit_store(store: SqliteRunStore | None) -> None:
    global _store
    _store = store


def audit(run_id: str, agent_id: str, state: Any, event: str, payload: dict[str, Any] | None = None) -> None:
    if not _store or not run_id:
        return
    sh = state_fingerprint(state)  # type: ignore[arg-type]
    _store.append_audit(run_id, agent_id, sh, event, payload)
