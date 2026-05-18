"""OPA/Rego policy evaluation (optional `opa` binary) with YAML fallback."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from gax.policy_bundle import PolicyDenied, check_policy_bundle
from gax.registry import CommandManifest

REGO_PATH = Path(__file__).resolve().parent.parent / "config" / "policy.rego"


def check_opa_or_yaml(
    claims: dict[str, Any],
    manifest: CommandManifest,
    args: dict[str, Any],
) -> None:
    if shutil.which("opa") and REGO_PATH.exists():
        inp = {
            "claims": claims,
            "command": manifest.command,
            "side_effects": manifest.side_effects,
            "args": args,
        }
        proc = subprocess.run(
            ["opa", "eval", "-d", str(REGO_PATH), "-I", "data", "data.gax.allow"],
            input=json.dumps({"input": inp}),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            try:
                val = json.loads(proc.stdout)
                allowed = val.get("result", [{}])[0].get("expressions", [{}])[0].get("value")
                if allowed is False:
                    raise PolicyDenied("OPA policy denied invoke")
                return
            except (json.JSONDecodeError, IndexError, KeyError):
                pass
    check_policy_bundle(claims, manifest, args)
