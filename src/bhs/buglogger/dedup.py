from __future__ import annotations

import hashlib
import re
from typing import Iterable

from bhs.state import BugSchema, BugType


def _normalize(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t[:500]


def bug_fingerprint(bug: BugSchema) -> str:
    btype = bug.type.value if isinstance(bug.type, BugType) else str(bug.type)
    key = "|".join(
        [
            btype,
            _normalize(bug.code_location or ""),
            _normalize(bug.root_cause or ""),
        ]
    )
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def dedupe_bugs(bugs: Iterable[BugSchema], similarity_threshold: float = 0.85) -> list[BugSchema]:
    """
    Deterministic dedup by fingerprint; embedding similarity can replace fingerprint bucket.
    """
    seen: dict[str, BugSchema] = {}
    for b in bugs:
        fp = bug_fingerprint(b)
        if fp not in seen:
            seen[fp] = b
        else:
            # merge: keep higher severity / CVSS
            cur = seen[fp]
            if float(b.cvss_score) > float(cur.cvss_score):
                seen[fp] = b
    _ = similarity_threshold  # reserved for embedding path
    return list(seen.values())
