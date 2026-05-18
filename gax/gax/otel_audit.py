from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from gax.paths import GAX_HOME, ensure_gax_home

OTEL_LOG_PATH = GAX_HOME / "audit.otel.jsonl"


def export_audit_event(
    *,
    audit_id: str,
    tenant_id: str,
    subject: str,
    command: str,
    ok: bool,
    duration_ms: float | None = None,
    error_kind: str | None = None,
) -> None:
    """Append OpenTelemetry-log-compatible JSON (stdout or file)."""
    if os.environ.get("GAX_OTEL_STDOUT") == "1":
        sink = None
    else:
        ensure_gax_home()
        sink = OTEL_LOG_PATH

    body = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity_text": "INFO" if ok else "ERROR",
        "body": f"gax.invoke {command}",
        "attributes": {
            "gax.audit_id": audit_id,
            "gax.tenant_id": tenant_id,
            "gax.subject": subject,
            "gax.command": command,
            "gax.ok": ok,
            "gax.duration_ms": duration_ms,
            "gax.error_kind": error_kind or "",
        },
        "trace_id": audit_id.replace("aud_", "")[:32].ljust(32, "0"),
    }
    line = json.dumps(body) + "\n"
    if sink is None:
        print(line, end="")
    else:
        with sink.open("a") as f:
            f.write(line)
