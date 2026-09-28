#!/usr/bin/env python3
"""
Security benchmark: does enforcement hold, and does it stay quiet when it should?

    python eval/run_security_eval.py                 # A + B (offline)
    python eval/run_security_eval.py --live          # + C (re-verify real MCP servers)

A. Side-effect ceiling — for every write/destructive command in the registry
   (bundled + profiles + imported MCP tools): a read-only capability that
   explicitly allowlists the command must be refused; a capability at the
   command's level must pass. Policy-only (check_invoke), so no real tool is
   ever executed. Plus an end-to-end refusal through the executor.
B. Pin tampering — a live stdio MCP server rewrites its own tool four ways;
   each must fail closed with pin_mismatch before the tool runs. Honest server
   is the control.
C. Pin false positives — re-verify every pin imported from real public MCP
   servers against the live servers. Any mismatch on an unchanged server is a
   false alarm, which trains people to ignore the check.

Writes eval/results/security-eval.{json,md}.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gax"))
os.environ.setdefault("GAX_K8S_MOCK", "1")  # never touch a real cluster

from gax.caps import decode_capability, mint_capability  # noqa: E402
from gax.executor import invoke  # noqa: E402
from gax.policy import PolicyDenied, check_invoke  # noqa: E402
from gax.registry import Registry  # noqa: E402
from gax.side_effects import normalize  # noqa: E402

OUT = ROOT / "eval" / "results"
MOCK = ROOT / "eval" / "mock_mcp" / "mutating_stdio_mock.py"
DEFAULT_REGISTRY = OUT / "mcp_registry"


def build_registry(extra: Path | None) -> Registry:
    reg = Registry(manifests_dir=ROOT / "gax" / "manifests")
    for d in (ROOT / "gax" / "profiles" / "k8s", ROOT / "gax" / "profiles" / "github", extra):
        if d and d.exists():
            reg._load_dir(d)
    return reg


def _claims(cmd, ceiling):
    return decode_capability(mint_capability(
        commands=[cmd.command], scopes=list(cmd.required_scopes) or ["*"],
        max_side_effect=ceiling))


def part_a(reg: Registry) -> dict:
    mutating = [m for m in reg.list_commands() if normalize(m.side_effects) != "read"]
    refused, allowed, leaks, blocks = 0, 0, [], []
    for m in mutating:
        try:
            check_invoke(_claims(m, "read"), m, {})
            leaks.append(m.command)  # read cap got through: a real failure
        except PolicyDenied:
            refused += 1
        try:
            check_invoke(_claims(m, normalize(m.side_effects)), m, {})
            allowed += 1
        except PolicyDenied as e:
            blocks.append(f"{m.command}: {e.message}")  # over-blocking: also a failure

    # End to end through the executor: refused before the adapter runs, audited.
    cap = mint_capability(commands=["k8s.namespace.delete"], scopes=["k8s:namespaces:write"],
                          max_side_effect="read")
    env, code = invoke(reg, command="k8s.namespace.delete", args={"namespace": "prod"},
                       capability=cap)
    e2e = {"ok": env["ok"], "kind": (env.get("error") or {}).get("kind"),
           "exit_code": code, "audited": bool(env.get("audit_id"))}

    levels = {lvl: sum(1 for m in mutating if normalize(m.side_effects) == lvl)
              for lvl in ("write", "destructive")}
    return {"commands_total": len(reg.list_commands()), "mutating": len(mutating),
            "by_level": levels, "read_cap_refused": refused,
            "correct_cap_allowed": allowed, "leaks": leaks, "over_blocks": blocks,
            "e2e_refusal": e2e}


def part_b(tmp: Path) -> dict:
    from gax.mcp_import import import_server

    target = tmp / "pin_manifests"
    import_server(server_id="demo", server_command=sys.executable,
                  server_args=[str(MOCK)], target_dir=target, force=True)
    reg = Registry(manifests_dir=target)
    cap = mint_capability(commands=["mcp.demo.read_file"], scopes=["mcp:demo:use"],
                          max_side_effect="read")
    results = {}
    for attack in ["honest", "description", "schema", "rename", "vanish"]:
        if attack == "honest":
            os.environ.pop("MOCK_MUTATE", None)
        else:
            os.environ["MOCK_MUTATE"] = attack
        env, code = invoke(reg, command="mcp.demo.read_file", args={"path": "/tmp/x"},
                           capability=cap)
        err = env.get("error") or {}
        results[attack] = {"ok": env["ok"], "kind": err.get("kind"),
                           "retryable": err.get("retryable"), "exit_code": code,
                           "audited": bool(env.get("audit_id"))}
    os.environ.pop("MOCK_MUTATE", None)
    attacks = [a for a in results if a != "honest"]
    return {"attacks": len(attacks),
            "refused": sum(results[a]["kind"] == "pin_mismatch" for a in attacks),
            "honest_passed": results["honest"]["ok"], "detail": results}


def part_c(registry_dir: Path) -> dict:
    from gax.mcp_import import verify_manifest_pins

    manifests = [yaml.safe_load(p.read_text()) for p in sorted(registry_dir.glob("*.yaml"))]
    manifests = [m for m in manifests if m and m.get("mcp_pin")]
    rows = verify_manifest_pins(manifests)
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {"pins": len(rows), "by_status": by_status,
            "false_alarms": [r for r in rows if r["status"] in ("mismatch", "missing")]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    ap.add_argument("--live", action="store_true", help="also re-verify real MCP servers")
    args = ap.parse_args()

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        os.environ["HOME"] = str(home)  # audit log goes here, not the user's ~/.gax
        import importlib

        import gax.audit
        import gax.executor
        import gax.paths
        importlib.reload(gax.paths)
        importlib.reload(gax.audit)
        importlib.reload(gax.executor)
        global invoke
        invoke = gax.executor.invoke

        extra = args.registry if args.registry.exists() else None
        report = {"generated_at": datetime.now(timezone.utc).isoformat(),
                  "registry_extra": str(extra) if extra else None,
                  "A_ceiling": part_a(build_registry(extra)),
                  "B_pin_tampering": part_b(Path(tmp))}
        if args.live and extra:
            report["C_pin_false_positives"] = part_c(extra)

    a, b = report["A_ceiling"], report["B_pin_tampering"]
    lines = ["# Security benchmark\n",
             f"\nGenerated {report['generated_at']} by `eval/run_security_eval.py`.\n",
             "\n## A. Side-effect ceiling\n",
             f"\n{a['mutating']} mutating commands of {a['commands_total']} "
             f"({a['by_level']['write']} write, {a['by_level']['destructive']} destructive).\n\n",
             "| Check | Result |\n|---|---:|\n",
             f"| Read-only capability refused (command explicitly allowlisted) | "
             f"**{a['read_cap_refused']}/{a['mutating']}** |\n",
             f"| Capability at the command's level allowed | "
             f"**{a['correct_cap_allowed']}/{a['mutating']}** |\n",
             f"| Leaks (read cap got through) | {len(a['leaks'])} |\n",
             f"| Over-blocks (correct cap refused) | {len(a['over_blocks'])} |\n",
             f"\nEnd to end: `k8s.namespace.delete` with a read-only capability → "
             f"`{a['e2e_refusal']['kind']}`, exit {a['e2e_refusal']['exit_code']}, "
             f"audited: {a['e2e_refusal']['audited']}.\n",
             "\n## B. Pin tampering (live stdio MCP server that mutates itself)\n\n",
             "| Server behaviour | ok | error kind | retryable | audited |\n|---|---|---|---|---|\n"]
    for k, v in b["detail"].items():
        lines.append(f"| {k} | {v['ok']} | {v['kind'] or '—'} | {v['retryable'] if v['kind'] else '—'} | {v['audited']} |\n")
    lines.append(f"\n**{b['refused']}/{b['attacks']} attacks refused before the tool ran**; "
                 f"honest server passed: {b['honest_passed']}.\n")
    if "C_pin_false_positives" in report:
        c = report["C_pin_false_positives"]
        lines += ["\n## C. Pin false positives (real public MCP servers)\n",
                  f"\n{c['pins']} pins re-verified against live servers: {c['by_status']}. "
                  f"False alarms: **{len(c['false_alarms'])}**.\n"]
    (OUT / "security-eval.json").write_text(json.dumps(report, indent=2, default=str))
    (OUT / "security-eval.md").write_text("".join(lines))
    print("".join(lines))

    failed = a["leaks"] or a["over_blocks"] or b["refused"] != b["attacks"] or not b["honest_passed"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
