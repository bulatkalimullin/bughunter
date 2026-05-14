from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from bhs.state import BHSState


class SqliteRunStore:
    """Durable run / state snapshots for HyperVisor."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    repo_hash TEXT,
                    created_at REAL,
                    updated_at REAL,
                    state_json TEXT,
                    status TEXT
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    ts REAL,
                    agent_id TEXT,
                    state_hash TEXT,
                    event TEXT,
                    payload_json TEXT
                )
                """
            )

    def create_run(self, repo_hash: str, initial: dict[str, Any]) -> str:
        run_id = str(uuid.uuid4())
        now = time.time()
        with self._connect() as c:
            c.execute(
                "INSERT INTO runs (run_id, repo_hash, created_at, updated_at, state_json, status) VALUES (?,?,?,?,?,?)",
                (run_id, repo_hash, now, now, json.dumps(initial), "running"),
            )
        return run_id

    def save_state(self, run_id: str, state: dict[str, Any], status: str = "running") -> None:
        now = time.time()
        with self._connect() as c:
            c.execute(
                "UPDATE runs SET state_json = ?, updated_at = ?, status = ? WHERE run_id = ?",
                (json.dumps(state), now, status, run_id),
            )

    def load_state(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as c:
            row = c.execute("SELECT state_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return json.loads(row["state_json"])

    def append_audit(
        self,
        run_id: str,
        agent_id: str,
        state_hash: str,
        event: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as c:
            c.execute(
                """
                INSERT INTO audit_log (run_id, ts, agent_id, state_hash, event, payload_json)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    run_id,
                    time.time(),
                    agent_id,
                    state_hash,
                    event,
                    json.dumps(payload or {}),
                ),
            )


def state_fingerprint(state: BHSState | dict[str, Any]) -> str:
    import hashlib

    if isinstance(state, dict):
        blob = json.dumps(state, sort_keys=True, default=str)
    else:
        blob = json.dumps(dict(state), sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
