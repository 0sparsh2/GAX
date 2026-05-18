"""SPIFFE / workload identity hooks for gaxd (MVP)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def workload_identity() -> dict[str, Any]:
    """Read SPIFFE material from env (set by tbot, SPIRE agent, or K8s CSI)."""
    cert = os.environ.get("GAX_SPIFFE_CERT_PATH", "")
    key = os.environ.get("GAX_SPIFFE_KEY_PATH", "")
    svid = os.environ.get("GAX_SPIFFE_SVID", "")
    spiffe_id = os.environ.get("GAX_SPIFFE_ID", "")
    out: dict[str, Any] = {
        "enabled": bool(cert or svid or spiffe_id),
        "spiffe_id": spiffe_id or None,
        "cert_present": bool(cert and Path(cert).exists()),
        "key_present": bool(key and Path(key).exists()),
    }
    if svid:
        out["svid_jwt_prefix"] = svid[:20] + "…"
    return out


def attest_metadata() -> dict[str, Any]:
    """Metadata attached to audit events when workload identity is configured."""
    wi = workload_identity()
    if not wi["enabled"]:
        return {}
    return {"workload_identity": wi}
