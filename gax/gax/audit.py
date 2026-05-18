from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from gax.paths import AUDIT_PATH, ensure_gax_home


def log_event(
    *,
    audit_id: str,
    tenant_id: str,
    subject: str,
    command: str,
    args: dict[str, Any],
    ok: bool,
    error_kind: str | None = None,
    duration_ms: float | None = None,
) -> None:
    ensure_gax_home()
    # Never log raw secrets; args should already be sanitized by caller
    safe_args = {k: v for k, v in args.items() if k.lower() not in ("token", "secret", "password")}
    from gax.spiffe import attest_metadata

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "audit_id": audit_id,
        "tenant_id": tenant_id,
        "subject": subject,
        "command": command,
        "args": safe_args,
        "ok": ok,
        "error_kind": error_kind,
        "duration_ms": duration_ms,
        **attest_metadata(),
    }
    with AUDIT_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")

    try:
        from gax.otel_audit import export_audit_event

        export_audit_event(
            audit_id=audit_id,
            tenant_id=tenant_id,
            subject=subject,
            command=command,
            ok=ok,
            duration_ms=duration_ms,
            error_kind=error_kind,
        )
    except Exception:
        pass
