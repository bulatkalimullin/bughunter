"""Ollama HTTP client for LLM-assisted test synthesis."""

from __future__ import annotations

import re
from typing import Any

import httpx

from bhs.config import Settings


def _strip_fences(text: str) -> str:
    t = text.strip()
    m = re.search(r"```(?:python)?\s*([\s\S]*?)```", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def generate_pytest_module(
    settings: Settings,
    *,
    language: str,
    hypothesis_set: list[str],
    findings_summary: str,
) -> str | None:
    """
    Call Ollama /api/chat. Returns Python source or None on failure.
    """
    if not settings.ollama_enabled:
        return None
    url = settings.ollama_base_url.rstrip("/") + "/api/chat"
    system = (
        "You are a test engineer. Output ONLY valid Python source code for a pytest file. "
        "No markdown, no explanations, no code fences. "
        "Include at least one test function. Use only stdlib and pytest."
    )
    user = (
        f"Language: {language}\n"
        f"Hypotheses (one per line):\n{chr(10).join(hypothesis_set[:50])}\n\n"
        f"Static findings summary:\n{findings_summary[:8000]}\n\n"
        "Write a small pytest module that adds regression tests relevant to the hypotheses."
    )
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    try:
        with httpx.Client(timeout=settings.ollama_timeout_sec) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None
    msg = data.get("message") or {}
    content = msg.get("content") if isinstance(msg, dict) else None
    if not isinstance(content, str) or not content.strip():
        return None
    body = _strip_fences(content)
    if not body.strip():
        return None
    return body
