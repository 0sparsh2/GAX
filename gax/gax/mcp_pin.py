"""
Schema pinning for imported MCP tools.

**The threat.** An MCP server is code someone else controls. It advertises its
tools at connect time, and it can advertise *different* tools tomorrow. A tool
called `search_files` that you reviewed and approved can later describe itself as
something else, or grow a `command` parameter, or have its description rewritten
to instruct the model to exfiltrate data. This is the tool-poisoning class behind
several of the 2026 MCP CVEs, and a proxy cannot catch it: a gateway forwards
whatever the server advertises.

**The pin.** At import time we hash the tool's *behavioural contract* — name,
description, and input schema — and store the digest in the manifest. Before every
invoke the live tool is hashed again and compared. A mismatch fails closed with
`pin_mismatch`; the call never reaches the server.

**What is hashed, and why exactly this.** The digest covers:

- `name` — a renamed tool is a different tool
- `description` — this is *instructions to the model*, so changing it changes agent
  behaviour even when the schema is untouched. This is the actual poisoning vector
  and the reason description is in scope.
- `inputSchema` — a new parameter is new capability

Everything else the server sends (title, annotations, output schema, vendor
extensions) is excluded: it varies harmlessly between versions and pinning it would
produce false alarms, which train people to disable the check.

JSON is serialized with sorted keys and no insignificant whitespace, so key order
and formatting differences do not move the digest. Hash is SHA-256 over UTF-8;
the digest is stored with an explicit `sha256:` prefix so the algorithm can be
changed later without ambiguity.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

PIN_ALGORITHM = "sha256"
PIN_PREFIX = f"{PIN_ALGORITHM}:"

# Fields that define the tool's contract with the model. Anything outside this set
# is presentation or metadata and must not trigger a mismatch.
PINNED_FIELDS = ("name", "description", "inputSchema")


class PinMismatch(Exception):
    """A live MCP tool no longer matches the pin recorded at import."""

    def __init__(self, tool: str, expected: str, actual: str, changed: list[str]) -> None:
        detail = ", ".join(changed) if changed else "unknown field"
        super().__init__(
            f"MCP tool '{tool}' changed since import ({detail}); "
            f"expected {expected}, got {actual}"
        )
        self.tool = tool
        self.expected = expected
        self.actual = actual
        self.changed = changed


def canonical_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """The subset of a tool definition that the pin covers."""
    return {
        "name": str(tool.get("name", "")),
        "description": str(tool.get("description") or ""),
        "inputSchema": tool.get("inputSchema") or {},
    }


def pin_tool(tool: dict[str, Any]) -> str:
    """Digest of a tool's behavioural contract, as `sha256:<hex>`."""
    payload = json.dumps(
        canonical_tool(tool),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return PIN_PREFIX + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def changed_fields(expected_tool: dict[str, Any], actual_tool: dict[str, Any]) -> list[str]:
    """Which pinned fields differ — for an error message a human can act on."""
    a, b = canonical_tool(expected_tool), canonical_tool(actual_tool)
    return [f for f in PINNED_FIELDS if a.get(f) != b.get(f)]


def verify_pin(
    tool: dict[str, Any],
    expected: str | None,
    *,
    expected_tool: dict[str, Any] | None = None,
) -> None:
    """
    Raise `PinMismatch` unless the live tool matches `expected`.

    A manifest with no pin raises too. Treating "unpinned" as "fine" would make
    the protection opt-out by omission — exactly the failure mode where someone
    hand-edits a manifest, drops the pin, and silently loses the check.
    """
    if not expected:
        raise PinMismatch(
            tool=str(tool.get("name", "?")),
            expected="(none recorded)",
            actual=pin_tool(tool),
            changed=["manifest has no mcp_pin"],
        )

    actual = pin_tool(tool)
    if _constant_time_equals(actual, expected):
        return

    changed = (
        changed_fields(expected_tool, tool)
        if expected_tool
        else ["name/description/inputSchema"]
    )
    raise PinMismatch(
        tool=str(tool.get("name", "?")),
        expected=expected,
        actual=actual,
        changed=changed,
    )


def _constant_time_equals(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a, b)


def find_tool(tools: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for tool in tools:
        if tool.get("name") == name:
            return tool
    return None
