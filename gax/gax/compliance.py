"""SOC2-friendly audit exports from ~/.gax/audit.jsonl."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gax.paths import AUDIT_PATH, GAX_HOME, ensure_gax_home

SOC2_FIELDS = [
    "timestamp",
    "audit_id",
    "tenant_id",
    "subject",
    "command",
    "ok",
    "error_kind",
    "duration_ms",
    "args_json",
]


def load_audit_lines(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or AUDIT_PATH
    if not p.exists():
        return []
    rows = []
    for line in p.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def export_soc2_csv(out_path: Path, *, since: str | None = None) -> int:
    rows = load_audit_lines()
    if since:
        rows = [r for r in rows if r.get("ts", "") >= since]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SOC2_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "timestamp": r.get("ts"),
                    "audit_id": r.get("audit_id"),
                    "tenant_id": r.get("tenant_id"),
                    "subject": r.get("subject"),
                    "command": r.get("command"),
                    "ok": r.get("ok"),
                    "error_kind": r.get("error_kind") or "",
                    "duration_ms": r.get("duration_ms") or "",
                    "args_json": json.dumps(r.get("args") or {}),
                }
            )
    return len(rows)


def export_soc2_json(out_path: Path) -> dict[str, Any]:
    rows = load_audit_lines()
    bundle = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "standard": "SOC2-aligned access log (MVP)",
        "record_count": len(rows),
        "records": rows,
    }
    out_path.write_text(json.dumps(bundle, indent=2))
    return bundle
