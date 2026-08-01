"""
Kubernetes exec adapter — the first commands in GAX with real blast radius.

Until now every registered command was `side_effects: read`, so the destructive
path through policy had never executed. These commands exist to make that path
real: `k8s.pod.delete` and `k8s.deployment.scale` can genuinely break a running
system, which is what makes the enforcement guarantee demonstrable rather than
architectural.

Three safety properties, in order of importance:

1. **`--dry-run` is honored server-side**, not by the caller. A dry run maps to
   `kubectl --dry-run=server` where kubectl supports it, so the API server
   validates without mutating.
2. **Args are passed as an argv list**, never through a shell. There is no string
   interpolation into a command line anywhere in this module, so a namespace of
   `; rm -rf /` is an invalid k8s name rather than an injection.
3. **Identifiers are validated** against the DNS-1123 subset kubectl accepts,
   before the subprocess is spawned.

`kubectl` absent → mock response, so tests and demos run without a cluster.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import Any

from gax.registry import CommandManifest

# DNS-1123: lowercase alphanumerics and '-', must start/end alphanumeric.
# Deliberately strict — anything outside this is rejected before exec.
_NAME_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
_MAX_NAME = 253

TIMEOUT_S = 60


class K8sArgError(ValueError):
    """Invalid Kubernetes identifier — raised before any subprocess runs."""


def _validate_name(value: Any, field: str) -> str:
    name = str(value or "").strip()
    if not name:
        raise K8sArgError(f"{field} is required")
    if len(name) > _MAX_NAME:
        raise K8sArgError(f"{field} exceeds {_MAX_NAME} characters")
    if not _NAME_RE.match(name):
        raise K8sArgError(
            f"invalid {field}: {name!r} (must match DNS-1123: lowercase "
            "alphanumeric and '-', starting and ending alphanumeric)"
        )
    return name


def _kubectl_available() -> bool:
    """
    Whether to drive real kubectl.

    `kubectl` being on PATH is not enough — it is commonly installed with no
    reachable cluster (CI, laptops), where every call fails with a connection
    error. `GAX_K8S_MOCK=1` forces the mock path so tests and demos are
    deterministic regardless of local kube context.
    """
    if os.environ.get("GAX_K8S_MOCK") == "1":
        return False
    return shutil.which("kubectl") is not None


def _run_kubectl(argv: list[str]) -> str:
    proc = subprocess.run(
        ["kubectl", *argv],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"kubectl {' '.join(argv)} failed")
    return proc.stdout


def run(
    manifest: CommandManifest,
    args: dict[str, Any],
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    dry_run = bool(args.get("dry_run"))

    name = _HANDLERS.get(manifest.command)
    if name is None:
        raise RuntimeError(f"k8s adapter has no handler for {manifest.command}")
    # Resolved by name at call time so monkeypatching a handler actually takes
    # effect; a table of function objects binds at import and silently ignores it.
    handler = globals()[name]
    if manifest.command in _MUTATING:
        return handler(args, dry_run=dry_run)
    return handler(args)


def _pod_list(args: dict[str, Any]) -> dict[str, Any]:
    namespace = _validate_name(args.get("namespace", "default"), "namespace")
    if not _kubectl_available():
        return {
            "items": [{"name": "mock-pod-1", "namespace": namespace, "status": "Running"}],
            "_mock": True,
        }
    out = _run_kubectl(["get", "pods", "-n", namespace, "-o", "json"])
    payload = json.loads(out or "{}")
    return {
        "items": [
            {
                "name": (i.get("metadata") or {}).get("name"),
                "namespace": namespace,
                "status": (i.get("status") or {}).get("phase"),
            }
            for i in payload.get("items", [])
        ]
    }


def _pod_delete(args: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    namespace = _validate_name(args.get("namespace", "default"), "namespace")
    pod = _validate_name(args.get("pod"), "pod")

    if not _kubectl_available():
        return {
            "deleted": not dry_run,
            "pod": pod,
            "namespace": namespace,
            "dry_run": dry_run,
            "_mock": True,
        }

    argv = ["delete", "pod", pod, "-n", namespace]
    if dry_run:
        argv.append("--dry-run=server")
    out = _run_kubectl(argv)
    return {
        "deleted": not dry_run,
        "pod": pod,
        "namespace": namespace,
        "dry_run": dry_run,
        "output": out.strip(),
    }


def _resource_list(kind: str, args: dict[str, Any]) -> dict[str, Any]:
    namespace = _validate_name(args.get("namespace", "default"), "namespace")
    if not _kubectl_available():
        return {
            "items": [{"name": f"mock-{kind}-1", "namespace": namespace}],
            "_mock": True,
        }
    payload = json.loads(_run_kubectl(["get", kind, "-n", namespace, "-o", "json"]) or "{}")
    return {
        "items": [
            {
                "name": (i.get("metadata") or {}).get("name"),
                "namespace": namespace,
            }
            for i in payload.get("items", [])
        ]
    }


def _deployment_list(args: dict[str, Any]) -> dict[str, Any]:
    return _resource_list("deployments", args)


def _service_list(args: dict[str, Any]) -> dict[str, Any]:
    return _resource_list("services", args)


def _pod_logs(args: dict[str, Any]) -> dict[str, Any]:
    namespace = _validate_name(args.get("namespace", "default"), "namespace")
    pod = _validate_name(args.get("pod"), "pod")
    tail = int(args.get("tail") or 100)
    if tail < 1:
        raise K8sArgError("tail must be >= 1")
    container = args.get("container")
    if container:
        container = _validate_name(container, "container")

    if not _kubectl_available():
        return {
            "pod": pod,
            "namespace": namespace,
            "lines": [f"[mock] log line for {pod}"],
            "_mock": True,
        }
    argv = ["logs", pod, "-n", namespace, f"--tail={tail}"]
    if container:
        argv += ["-c", container]
    out = _run_kubectl(argv)
    return {
        "pod": pod,
        "namespace": namespace,
        "lines": out.splitlines(),
    }


def _pod_describe(args: dict[str, Any]) -> dict[str, Any]:
    namespace = _validate_name(args.get("namespace", "default"), "namespace")
    pod = _validate_name(args.get("pod"), "pod")
    if not _kubectl_available():
        return {"pod": pod, "namespace": namespace, "status": "Running", "_mock": True}
    payload = json.loads(_run_kubectl(["get", "pod", pod, "-n", namespace, "-o", "json"]) or "{}")
    status = payload.get("status") or {}
    return {
        "pod": pod,
        "namespace": namespace,
        "status": status.get("phase"),
        "conditions": [
            {"type": c.get("type"), "status": c.get("status")}
            for c in status.get("conditions", [])
        ],
        "containers": [
            {"name": c.get("name"), "ready": c.get("ready"), "restarts": c.get("restartCount")}
            for c in status.get("containerStatuses", [])
        ],
    }


def _deployment_restart(args: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    namespace = _validate_name(args.get("namespace", "default"), "namespace")
    deployment = _validate_name(args.get("deployment"), "deployment")
    if not _kubectl_available():
        return {
            "restarted": not dry_run,
            "deployment": deployment,
            "namespace": namespace,
            "dry_run": dry_run,
            "_mock": True,
        }
    argv = ["rollout", "restart", f"deployment/{deployment}", "-n", namespace]
    if dry_run:
        argv.append("--dry-run=server")
    out = _run_kubectl(argv)
    return {
        "restarted": not dry_run,
        "deployment": deployment,
        "namespace": namespace,
        "dry_run": dry_run,
        "output": out.strip(),
    }


def _namespace_delete(args: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    namespace = _validate_name(args.get("namespace"), "namespace")
    if not _kubectl_available():
        return {
            "deleted": not dry_run,
            "namespace": namespace,
            "dry_run": dry_run,
            "_mock": True,
        }
    argv = ["delete", "namespace", namespace]
    if dry_run:
        argv.append("--dry-run=server")
    out = _run_kubectl(argv)
    return {
        "deleted": not dry_run,
        "namespace": namespace,
        "dry_run": dry_run,
        "output": out.strip(),
    }


def _deployment_scale(args: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    namespace = _validate_name(args.get("namespace", "default"), "namespace")
    deployment = _validate_name(args.get("deployment"), "deployment")

    raw = args.get("replicas")
    if raw is None:
        raise K8sArgError("replicas is required")
    try:
        replicas = int(raw)
    except (TypeError, ValueError):
        raise K8sArgError(f"replicas must be an integer, got {raw!r}") from None
    if replicas < 0:
        raise K8sArgError("replicas must be >= 0")

    if not _kubectl_available():
        return {
            "scaled": not dry_run,
            "deployment": deployment,
            "namespace": namespace,
            "replicas": replicas,
            "dry_run": dry_run,
            "_mock": True,
        }

    argv = [
        "scale",
        f"deployment/{deployment}",
        f"--replicas={replicas}",
        "-n",
        namespace,
    ]
    if dry_run:
        argv.append("--dry-run=server")
    out = _run_kubectl(argv)
    return {
        "scaled": not dry_run,
        "deployment": deployment,
        "namespace": namespace,
        "replicas": replicas,
        "dry_run": dry_run,
        "output": out.strip(),
    }


# Dispatch table. Mutating commands receive `dry_run`; read-only ones do not —
# so a read command can never silently accept a dry_run it would ignore.
_HANDLERS = {
    "k8s.pod.list": "_pod_list",
    "k8s.pod.logs": "_pod_logs",
    "k8s.pod.describe": "_pod_describe",
    "k8s.deployment.list": "_deployment_list",
    "k8s.service.list": "_service_list",
    "k8s.pod.delete": "_pod_delete",
    "k8s.deployment.scale": "_deployment_scale",
    "k8s.deployment.restart": "_deployment_restart",
    "k8s.namespace.delete": "_namespace_delete",
}

_MUTATING = {
    "k8s.pod.delete",
    "k8s.deployment.scale",
    "k8s.deployment.restart",
    "k8s.namespace.delete",
}
