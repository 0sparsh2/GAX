#!/usr/bin/env python3
"""
Build the "real-world registry" used by the search and security benchmarks.

Imports five public MCP servers into a directory as pinned GAX manifests:

    python eval/import_mcp_servers.py eval/results/mcp_registry

Servers are fetched with `npx -y`, i.e. whatever version is current, so tool
counts can drift over time. The run writes a snapshot (server -> tool count and
pins) next to the manifests so every published number can be traced to the exact
tool set it was measured on.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gax"))

from gax.mcp_import import import_server  # noqa: E402

SERVERS = [
    ("filesystem", "@modelcontextprotocol/server-filesystem", ["/tmp"]),
    ("memory", "@modelcontextprotocol/server-memory", []),
    ("everything", "@modelcontextprotocol/server-everything", []),
    ("firecrawl", "firecrawl-mcp", []),
    ("context7", "@upstash/context7-mcp", []),
]


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "eval" / "results" / "mcp_registry"
    target.mkdir(parents=True, exist_ok=True)
    snapshot = {"imported_at": datetime.now(timezone.utc).isoformat(), "servers": {}}
    for sid, pkg, extra in SERVERS:
        try:
            r = import_server(server_id=sid, server_command="npx",
                              server_args=["-y", pkg, *extra], target_dir=target, force=True)
            snapshot["servers"][sid] = {
                "package": pkg,
                "tools": len(r["written"]),
                "side_effects": {
                    lvl: sum(1 for w in r["written"] if w["side_effects"] == lvl)
                    for lvl in ("read", "write", "destructive")
                },
                "pins": {w["command"]: w["pin"] for w in r["written"]},
            }
            print(f"  ✓ {sid:12} {len(r['written']):>3} tools")
        except Exception as e:  # a server being unreachable is recorded, not fatal
            snapshot["servers"][sid] = {"package": pkg, "error": str(e)}
            print(f"  ✗ {sid:12} {e}")
    (target / "snapshot.json").write_text(json.dumps(snapshot, indent=2))
    total = sum(s.get("tools", 0) for s in snapshot["servers"].values())
    print(f"\n  {total} tools from {len(SERVERS)} servers → {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
