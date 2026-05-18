from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

import yaml

from gax.envelope import make_envelope, timed_meta
from gax.executor import invoke
from gax.registry import Registry

_TEMPLATE = re.compile(r"\{\{\s*([^}]+)\s*\}\}")


def load_plan(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_path(expr: str, ctx: dict[str, Any]) -> Any:
    parts = expr.strip().split(".")
    cur: Any = ctx
    for p in parts:
        if p.endswith("]"):
            key, idx = p[:-1].split("[")
            cur = cur[key][int(idx)]
        elif "[" in p:
            key, rest = p.split("[", 1)
            idx = int(rest.rstrip("]"))
            cur = cur[key][idx]
        else:
            cur = cur[p]
    return cur


def render_value(value: Any, ctx: dict[str, Any]) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        m = re.fullmatch(r"\{\{\s*([^}]+)\s*\}\}", stripped)
        if m:
            return _resolve_path(m.group(1), ctx)

        def repl(match: re.Match[str]) -> str:
            resolved = _resolve_path(match.group(1), ctx)
            return str(resolved)

        return _TEMPLATE.sub(repl, value)
    if isinstance(value, dict):
        return {k: render_value(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [render_value(v, ctx) for v in value]
    return value


def _run_step(
    step: dict[str, Any],
    ctx: dict[str, Any],
    surface: str,
    invoke_fn: Callable[..., tuple[dict[str, Any], int]],
) -> tuple[str, dict[str, Any], int]:
    step_id = step.get("id") or step.get("command")
    command = step["command"]
    args = render_value(step.get("args") or {}, ctx)
    env, code = invoke_fn(command=command, args=args, surface=surface)
    ctx["steps"][step_id] = {
        "ok": env.get("ok"),
        "data": env.get("data"),
        "meta": env.get("meta"),
        "audit_id": env.get("audit_id"),
    }
    summary = {
        "id": step_id,
        "command": command,
        "ok": env.get("ok"),
        "audit_id": env.get("audit_id"),
    }
    return step_id, summary, code


def run_plan(
    registry: Registry,
    plan: dict[str, Any],
    *,
    surface: str = "model",
    capability: str | None = None,
    invoke_fn: Callable[..., tuple[dict[str, Any], int]] | None = None,
) -> tuple[dict[str, Any], int]:
    """Execute plan steps (sequential or parallel groups)."""
    start = time.perf_counter()
    steps_def = plan.get("steps") or []
    if not steps_def:
        return make_envelope(
            ok=False,
            cmd="plan@1",
            surface=surface,
            data={},
            error={"kind": "invalid_plan", "message": "no steps", "retryable": False},
        ), 1

    invoke_fn = invoke_fn or (lambda **kw: invoke(registry, capability=capability, **kw))
    ctx: dict[str, Any] = {"steps": {}}
    step_results: list[dict[str, Any]] = []
    last_env: dict[str, Any] | None = None
    exit_code = 0

    for block in steps_def:
        if "parallel" in block:
            branches = block["parallel"]
            with ThreadPoolExecutor(max_workers=min(8, len(branches))) as pool:
                futures = {
                    pool.submit(_run_step, branch, ctx, surface, invoke_fn): branch
                    for branch in branches
                }
                for fut in as_completed(futures):
                    _sid, summary, code = fut.result()
                    step_results.append(summary)
                    if code != 0 or not summary.get("ok"):
                        exit_code = code or 1
            if exit_code:
                break
            continue

        step_id, summary, code = _run_step(block, ctx, surface, invoke_fn)
        step_results.append(summary)
        last_env = ctx["steps"][step_id]
        if code != 0 or not summary.get("ok"):
            exit_code = code or 1
            break

    combined = make_envelope(
        ok=exit_code == 0,
        cmd=f"plan:{plan.get('name', 'unnamed')}@1",
        surface=surface,
        data={
            "steps": ctx["steps"],
            "summary": step_results,
            "final": (
                ctx["steps"][step_results[-1]["id"]].get("data", {})
                if step_results and step_results[-1]["id"] in ctx["steps"]
                else {}
            ),
        },
        schema="https://schemas.gax.dev/plan/result/v1",
        meta=timed_meta(start, step_count=len(step_results)),
        error={"kind": "plan_failed", "message": "one or more steps failed", "retryable": True}
        if exit_code
        else None,
    )
    return combined, exit_code
