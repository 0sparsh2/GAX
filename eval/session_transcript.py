"""Simulate multi-turn agent transcripts for token measurement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from token_count import count_json, count_tokens


@dataclass
class Transcript:
    messages: list[dict[str, str]] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def add_json(self, role: str, obj: Any) -> None:
        import json

        self.add(role, json.dumps(obj, ensure_ascii=False))

    def total_tokens(self) -> int:
        return sum(count_tokens(m["content"]) for m in self.messages)


def cli_turn(transcript: Transcript, *, system: str, command: str, output: str) -> None:
    transcript.add("system", system)
    transcript.add("assistant", command)
    transcript.add("tool", output[:8000])


def mcp_naive_turn(
    transcript: Transcript,
    *,
    system: str,
    schema_blob: str,
    tool_call: str,
    output: str,
) -> None:
    transcript.add("system", system)
    transcript.add("system", schema_blob)  # full tools/list each session
    transcript.add("assistant", tool_call)
    transcript.add("tool", output[:8000])


def gax_turn(
    transcript: Transcript,
    *,
    system: str,
    doc_stub: str,
    command: str,
    envelope: dict[str, Any],
) -> None:
    transcript.add("system", system)
    transcript.add("assistant", doc_stub)
    transcript.add("assistant", command)
    transcript.add_json("tool", envelope)


def gax_raw_turn(
    transcript: Transcript,
    *,
    system: str,
    doc_stub: str,
    command: str,
    raw_output: str,
) -> None:
    """Ablation: invoke path without envelope v1 in agent context (raw tool text)."""
    transcript.add("system", system)
    transcript.add("assistant", doc_stub)
    transcript.add("assistant", command)
    transcript.add("tool", raw_output[:8000])


def programmatic_mcp_turn(
    transcript: Transcript,
    *,
    system: str,
    code_snippet: str,
    tool_output: str,
    schema_tokens: int,
) -> int:
    """
    Optimized MCP / code-mode style: tiny tool surface (2 logical tools) + code,
    not full tools/list in context. Returns total tokens including schema_tax.
    """
    transcript.add("system", system)
    transcript.add(
        "system",
        "[MCP code mode: tools search() + execute() — schema omitted; "
        f"~{schema_tokens} tok session overhead]",
    )
    transcript.add("assistant", code_snippet)
    transcript.add("tool", tool_output[:8000])
    return transcript.total_tokens() + schema_tokens


def cli_agent_spec_turn(
    transcript: Transcript,
    *,
    system: str,
    command: str,
    exit_code: int,
    stdout: str,
    stderr: str,
) -> None:
    """CLI Agent Spec–style structured result (not GAX envelope)."""
    import json

    transcript.add("system", system)
    transcript.add("assistant", command)
    payload = {
        "spec": "cli-agent-result/v1",
        "exit_code": exit_code,
        "stdout": stdout[:6000],
        "stderr": stderr[:2000],
    }
    transcript.add("tool", json.dumps(payload, ensure_ascii=False))


def cli_logged_turn(
    transcript: Transcript,
    *,
    system: str,
    command: str,
    output: str,
    audit_id: str | None = None,
) -> None:
    """gh + post-hoc logging proxy: shell output plus synthetic log line (not pre-invoke enforce)."""
    import json

    transcript.add("system", system)
    transcript.add("assistant", command)
    transcript.add("tool", output[:8000])
    transcript.add(
        "tool",
        json.dumps(
            {
                "proxy_log": True,
                "audit_id": audit_id or "proxy_aud_synthetic",
                "note": "logged after command completed",
            }
        ),
    )
