"""
`gax init` and `gax doctor` — the on-ramp.

We measured the pre-existing first-run path in a clean virtualenv: a new engineer
hit **two dead ends** before their first successful command. `gax demo.echo` returned
a bare `[Errno 61] Connection refused` with no hint the sidecar wasn't running, and
`gax --local demo.echo` then failed with `missing capability token`. Both are
correct behavior and both are useless as a first experience.

`init` collapses that into one command. `doctor` diagnoses the same failures after
the fact. Neither invents state silently: `init` reports exactly what it did, and is
idempotent so re-running is safe.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gax.paths import (
    AUDIT_PATH,
    CONFIG_PATH,
    DEFAULT_HOST,
    DEFAULT_PORT,
    GAX_HOME,
    PID_PATH,
    ensure_gax_home,
)

CAP_PATH = GAX_HOME / "dev_cap.jwt"

# Enough to be useful immediately, all read-only. Destructive commands are
# deliberately excluded: a dev capability minted by `init` must not be able to
# delete anything, and raising its ceiling should be a conscious act.
DEV_COMMANDS = [
    "demo.echo",
    "gh.pr.list",
    "gh.pr.view",
    "k8s.pod.list",
    "kubectl.get.pods",
    "aws.s3.list",
    "jira.issue.get",
]
DEV_SCOPES = [
    "demo:echo",
    "github:pull_request:read",
    "k8s:pods:read",
    "aws:s3:read",
    "jira:issue:read",
]
DEV_TTL_SECONDS = 30 * 24 * 3600  # 30 days — long enough to not derail a trial


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""

    @property
    def symbol(self) -> str:
        return "✓" if self.ok else "✗"


def daemon_health(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict[str, Any] | None:
    try:
        import httpx

        r = httpx.get(f"http://{host}:{port}/health", timeout=1.5)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def daemon_running(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    return daemon_health(host, port) is not None


def config_fingerprint() -> str:
    """Fingerprint of the local signing secret — never the secret itself."""
    import hashlib

    from gax.caps import jwt_secret

    return hashlib.sha256(jwt_secret().encode()).hexdigest()[:12]


def daemon_config_matches(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool | None:
    """
    Whether a running daemon shares our signing secret.

    A daemon started against a different `~/.gax` accepts connections but rejects
    every capability with "Signature verification failed" — a confusing failure
    that looks like a broken token rather than a stale process. `None` means the
    daemon is unreachable or too old to report a fingerprint.
    """
    health = daemon_health(host, port)
    if not health:
        return None
    remote = health.get("config_fingerprint")
    if not remote:
        return None
    return remote == config_fingerprint()


def _start_daemon(host: str, port: int) -> bool:
    """Spawn gaxd detached. Returns True once /health answers."""
    exe = shutil.which("gaxd")
    cmd = [exe, "start"] if exe else [sys.executable, "-m", "gax.daemon", "start"]
    try:
        subprocess.Popen(
            [*cmd, "--host", host, "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        return False
    for _ in range(30):  # up to ~6s
        if daemon_running(host, port):
            return True
        time.sleep(0.2)
    return False


def _cap_claims(token: str) -> dict[str, Any] | None:
    try:
        from gax.caps import decode_capability

        return decode_capability(token)
    except Exception:
        return None


def read_saved_cap() -> str | None:
    if not CAP_PATH.exists():
        return None
    token = CAP_PATH.read_text().strip()
    return token or None


def run_init(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    start_daemon: bool = True,
    force: bool = False,
    profiles: list[str] | None = None,
) -> dict[str, Any]:
    """
    Idempotent setup. Returns a report rather than printing, so the CLI owns
    presentation and tests can assert on structure.
    """
    steps: list[str] = []
    ensure_gax_home()
    steps.append(f"created {GAX_HOME}")

    # Profiles first: the capability minted below should cover what got installed.
    installed_profiles: list[dict[str, Any]] = []
    for name in profiles or []:
        from gax.profiles import install_profile

        try:
            result = install_profile(name, force=force)
        except KeyError:
            steps.append(f"unknown profile '{name}' — skipped")
            continue
        installed_profiles.append(result)
        n = len(result["installed"])
        detail = f"installed profile '{name}' ({n} commands: {result['summary']})"
        if result["skipped"]:
            detail += f", {len(result['skipped'])} already present"
        steps.append(detail)

    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            json.dumps(
                {
                    "jwt_secret": os.urandom(24).hex(),
                    "tenant_id": "default",
                    "subject": "dev@local",
                },
                indent=2,
            )
        )
        steps.append("wrote config.json (random dev signing secret)")
    else:
        steps.append("config.json already present — kept")

    # Mint only when missing or expired, so re-running init doesn't invalidate a
    # capability the user already exported into their shell.
    from gax.caps import mint_capability

    # Cover the profile's read-only commands too, otherwise `init --profile k8s`
    # registers commands the dev capability cannot call. Write/destructive commands
    # are deliberately NOT added: the ceiling stays `read`, so reaching them
    # requires minting a capability on purpose.
    commands = list(DEV_COMMANDS)
    scopes = list(DEV_SCOPES)
    for result in installed_profiles:
        from gax.profiles import get_profile

        profile = get_profile(result["profile"])
        if not profile:
            continue
        for cmd in profile.by_level("read"):
            if cmd.command not in commands:
                commands.append(cmd.command)
            for scope in cmd.required_scopes:
                if scope not in scopes:
                    scopes.append(scope)

    existing = read_saved_cap()
    reuse = bool(existing) and not force and _cap_claims(existing or "") is not None
    # A profile installed after the capability was minted needs a re-mint, or its
    # read commands would be registered but uncallable.
    if reuse and installed_profiles:
        claims = _cap_claims(existing or "") or {}
        held = set(claims.get("commands") or [])
        if not set(commands).issubset(held):
            reuse = False

    if reuse:
        token = existing or ""
        steps.append("dev capability still valid — kept")
    else:
        token = mint_capability(
            commands=commands,
            scopes=scopes,
            ttl_seconds=DEV_TTL_SECONDS,
            max_side_effect="read",
        )
        CAP_PATH.write_text(token)
        CAP_PATH.chmod(0o600)
        steps.append(
            f"minted 30-day read-only dev capability ({len(commands)} commands) → {CAP_PATH}"
        )

    daemon_ok = daemon_running(host, port)
    stale_daemon = False
    if daemon_ok:
        if daemon_config_matches(host, port) is False:
            # Running, but signed with a different secret — every invoke would
            # fail with "Signature verification failed". Report it loudly here
            # rather than let the user debug a token that is actually fine.
            stale_daemon = True
            steps.append(
                f"gaxd on {host}:{port} uses a DIFFERENT config — "
                "restart it: gaxd stop && gaxd start --background"
            )
        else:
            steps.append(f"gaxd already running on {host}:{port}")
    elif start_daemon:
        daemon_ok = _start_daemon(host, port)
        steps.append(
            f"started gaxd on {host}:{port}" if daemon_ok else "could not start gaxd"
        )

    return {
        "gax_home": str(GAX_HOME),
        "capability_path": str(CAP_PATH),
        "capability": token,
        "daemon_running": daemon_ok,
        "daemon_config_mismatch": stale_daemon,
        "host": host,
        "port": port,
        "steps": steps,
        "commands": DEV_COMMANDS,
    }


def run_doctor(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> list[Check]:
    """Diagnose the failures a first-run user actually hits."""
    checks: list[Check] = []

    checks.append(
        Check(
            "gax home",
            GAX_HOME.exists(),
            str(GAX_HOME) if GAX_HOME.exists() else "missing",
            fix="run: gax init",
        )
    )

    checks.append(
        Check(
            "config",
            CONFIG_PATH.exists(),
            "config.json present" if CONFIG_PATH.exists() else "missing",
            fix="run: gax init",
        )
    )

    # Registry
    try:
        from gax.registry import Registry

        n = len(Registry().list_commands())
        checks.append(Check("registry", n > 0, f"{n} commands registered",
                            fix="check manifests/ directory"))
    except Exception as e:
        checks.append(Check("registry", False, f"failed to load: {e}"))

    # Capability: env wins over saved file, since that is what invokes actually use.
    env_cap = os.environ.get("GAX_CAP", "").strip()
    saved = read_saved_cap()
    token = env_cap or saved or ""
    source = "GAX_CAP env" if env_cap else ("~/.gax/dev_cap.jwt" if saved else "none")
    if not token:
        checks.append(
            Check("capability", False, "no capability found",
                  fix="run: gax init, then eval \"$(gax init --print-export)\"")
        )
    else:
        claims = _cap_claims(token)
        if claims is None:
            checks.append(
                Check("capability", False, f"invalid or expired ({source})",
                      fix="run: gax init --force")
            )
        else:
            exp = claims.get("exp")
            left = int(exp - time.time()) if isinstance(exp, (int, float)) else None
            detail = f"valid from {source}"
            if left is not None:
                detail += f", expires in {left // 86400}d {left % 86400 // 3600}h"
            detail += f", ceiling={claims.get('max_side_effect', 'read')}"
            checks.append(Check("capability", True, detail))
            if not env_cap and saved:
                # Not a failure: the CLI falls back to the saved capability, so
                # commands work without exporting. Only other tools (raw HTTP,
                # the MCP server under some launchers) need the env var, so this
                # is informational — flagging it red would be a false alarm.
                checks.append(
                    Check(
                        "GAX_CAP env",
                        True,
                        'not set; CLI uses ~/.gax/dev_cap.jwt. For other tools: '
                        'eval "$(gax init --print-export)"',
                    )
                )

    running = daemon_running(host, port)
    checks.append(
        Check(
            "gaxd sidecar",
            running,
            f"responding on {host}:{port}" if running else f"not reachable on {host}:{port}",
            fix="run: gaxd start --background   (or use: gax --local <cmd>)",
        )
    )
    if running and daemon_config_matches(host, port) is False:
        checks.append(
            Check(
                "gaxd config",
                False,
                "daemon is using a different signing secret — every invoke will "
                "fail with 'Signature verification failed'",
                fix="run: gaxd stop && gaxd start --background",
            )
        )

    # Backends — informational; absence falls back to mocks rather than failing.
    for binary, why in (("gh", "gh.pr.* commands"), ("kubectl", "k8s.* commands")):
        found = shutil.which(binary)
        checks.append(
            Check(
                f"{binary} binary",
                bool(found),
                found or f"not found — {why} will return mock data",
                fix=f"install {binary} for live {why}",
            )
        )

    checks.append(
        Check(
            "audit log",
            True,
            f"{AUDIT_PATH} ({AUDIT_PATH.stat().st_size} bytes)"
            if AUDIT_PATH.exists()
            else "no invocations recorded yet",
        )
    )

    return checks
