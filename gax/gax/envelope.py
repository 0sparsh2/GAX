from __future__ import annotations

import time
import uuid
from typing import Any


def new_audit_id() -> str:
    return f"aud_{uuid.uuid4().hex[:16]}"


def make_envelope(
    *,
    ok: bool,
    cmd: str,
    surface: str,
    data: Any,
    audit_id: str | None = None,
    schema: str | None = None,
    meta: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    next_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    env: dict[str, Any] = {
        "v": 1,
        "ok": ok,
        "cmd": cmd,
        "audit_id": audit_id or new_audit_id(),
        "surface": surface,
        "data": data if data is not None else {},
        "meta": meta or {},
        "error": error,
    }
    if schema:
        env["schema"] = schema
    if next_actions:
        env["next"] = next_actions
    return env


def fail_envelope(
    *,
    cmd: str,
    surface: str,
    kind: str,
    message: str,
    retryable: bool = False,
    audit_id: str | None = None,
) -> dict[str, Any]:
    return make_envelope(
        ok=False,
        cmd=cmd,
        surface=surface,
        data={},
        audit_id=audit_id,
        error={"kind": kind, "message": message, "retryable": retryable},
        meta={"duration_ms": 0},
    )


def timed_meta(start: float, **extra: Any) -> dict[str, Any]:
    meta = {"duration_ms": round((time.perf_counter() - start) * 1000, 2)}
    meta.update(extra)
    return meta
