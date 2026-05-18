from __future__ import annotations

import time
from typing import Any

from gax.adapters.base import run_adapter
from gax.audit import log_event
from gax.caps import decode_capability
from gax.envelope import fail_envelope, make_envelope, timed_meta
from gax.policy import PolicyDenied, check_invoke
from gax.projection import project_data
from gax.registry import Registry


def invoke(
    registry: Registry,
    *,
    command: str,
    args: dict[str, Any],
    surface: str = "model",
    capability: str | None = None,
) -> tuple[dict[str, Any], int]:
    start = time.perf_counter()
    manifest = registry.get(command)
    cmd_label = f"{command}@?" if not manifest else manifest.cmd_id

    try:
        claims = decode_capability(capability)
    except Exception as e:
        env = fail_envelope(
            cmd=cmd_label,
            surface=surface,
            kind="capability_invalid",
            message=str(e),
        )
        return env, 3

    tenant_id = str(claims.get("tenant_id", "unknown"))
    subject = str(claims.get("sub", "unknown"))

    if not manifest:
        env = fail_envelope(
            cmd=cmd_label,
            surface=surface,
            kind="not_found",
            message=f"unknown command: {command}",
        )
        log_event(
            audit_id=env["audit_id"],
            tenant_id=tenant_id,
            subject=subject,
            command=command,
            args=args,
            ok=False,
            error_kind="not_found",
        )
        return env, 4

    cmd_label = manifest.cmd_id
    try:
        check_invoke(claims, manifest, args)
    except PolicyDenied as e:
        env = fail_envelope(
            cmd=cmd_label,
            surface=surface,
            kind="policy_denied",
            message=e.message,
            retryable=False,
        )
        log_event(
            audit_id=env["audit_id"],
            tenant_id=tenant_id,
            subject=subject,
            command=command,
            args=args,
            ok=False,
            error_kind="policy_denied",
        )
        return env, 2

    audit_id = make_envelope(ok=True, cmd=cmd_label, surface=surface, data={})["audit_id"]

    try:
        raw = run_adapter(manifest, args, tenant_id=tenant_id)
    except Exception as e:
        env = fail_envelope(
            cmd=cmd_label,
            surface=surface,
            kind="adapter_error",
            message=str(e),
            retryable=True,
            audit_id=audit_id,
        )
        log_event(
            audit_id=audit_id,
            tenant_id=tenant_id,
            subject=subject,
            command=command,
            args=args,
            ok=False,
            error_kind="adapter_error",
            duration_ms=timed_meta(start)["duration_ms"],
        )
        return env, 5

    projected, proj_meta = project_data(raw, surface)
    meta = timed_meta(start, **proj_meta)

    next_actions = None
    if manifest.command == "gh.pr.list" and isinstance(projected, dict):
        items = projected.get("items") or []
        if items:
            first = items[0]
            next_actions = [
                {
                    "cmd": "gh.pr.view",
                    "args": {"repo": args.get("repo"), "number": first.get("number")},
                    "reason": "inspect first PR in list",
                }
            ]

    env = make_envelope(
        ok=True,
        cmd=cmd_label,
        surface=surface,
        data=projected,
        audit_id=audit_id,
        schema=manifest.schema_uri,
        meta=meta,
        next_actions=next_actions,
    )

    log_event(
        audit_id=audit_id,
        tenant_id=tenant_id,
        subject=subject,
        command=command,
        args=args,
        ok=True,
        duration_ms=meta.get("duration_ms"),
    )
    return env, 0
