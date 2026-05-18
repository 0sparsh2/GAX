from __future__ import annotations

import copy
from typing import Any

MODEL_MAX_ROWS = 10
MODEL_MAX_STRING = 500
REDACT_KEYS = {"token", "secret", "password", "authorization"}


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k.lower() in REDACT_KEYS:
                out[k] = "[redacted]"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, str) and len(obj) > MODEL_MAX_STRING:
        return obj[:MODEL_MAX_STRING] + "…"
    return obj


def project_data(data: Any, surface: str) -> tuple[Any, dict[str, Any]]:
    meta: dict[str, Any] = {}
    if surface == "full":
        return data, meta

    if surface not in ("model", "human"):
        surface = "model"

    projected = _redact(copy.deepcopy(data))
    if isinstance(projected, dict) and "items" in projected and isinstance(projected["items"], list):
        items = projected["items"]
        if len(items) > MODEL_MAX_ROWS:
            projected["items"] = items[:MODEL_MAX_ROWS]
            meta["truncated"] = True
            meta["row_count"] = len(items)
    return projected, meta
