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
