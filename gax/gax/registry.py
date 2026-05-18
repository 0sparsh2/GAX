from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from gax.paths import MANIFESTS_DIR


@dataclass
class CommandManifest:
    command: str
    version: str
    description: str
    category: str
    adapter: str
    backend: list[str] = field(default_factory=list)
    required_scopes: list[str] = field(default_factory=list)
    side_effects: str = "read"
    idempotent: bool = True
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def cmd_id(self) -> str:
        return f"{self.command}@{self.version}"

    @property
    def schema_uri(self) -> str:
        return f"https://schemas.gax.dev/{self.command.replace('.', '/')}/v{self.version.split('.')[0]}"


class Registry:
    def __init__(self, manifests_dir: Path | None = None) -> None:
        self._dir = manifests_dir or MANIFESTS_DIR
        self._commands: dict[str, CommandManifest] = {}
        self.reload()

    def reload(self) -> None:
        self._commands.clear()
        if not self._dir.exists():
            return
        for path in sorted(self._dir.glob("*.yaml")):
            data = yaml.safe_load(path.read_text()) or {}
            cmd = data.get("command")
            if not cmd:
                continue
            self._commands[cmd] = CommandManifest(
                command=cmd,
                version=str(data.get("version", "1.0.0")),
                description=str(data.get("description", "")),
                category=str(data.get("category", "general")),
                adapter=str(data.get("adapter", "mock")),
                backend=list(data.get("backend") or []),
                required_scopes=list(data.get("required_scopes") or []),
                side_effects=str(data.get("side_effects", "read")),
                idempotent=bool(data.get("idempotent", True)),
                input_schema=dict(data.get("input_schema") or {}),
                output_schema=dict(data.get("output_schema") or {}),
                raw=data,
            )

    def get(self, command: str) -> CommandManifest | None:
        return self._commands.get(command)

    def list_commands(self) -> list[CommandManifest]:
        return list(self._commands.values())

    def search(self, query: str, limit: int = 5) -> list[CommandManifest]:
        q = query.lower().strip()
        if not q:
            return self.list_commands()[:limit]
        scored: list[tuple[int, CommandManifest]] = []
        for m in self._commands.values():
            hay = f"{m.command} {m.description} {m.category}".lower()
            score = 0
            if q in m.command.lower():
                score += 10
            if q in m.description.lower():
                score += 5
            for word in q.split():
                if word in hay:
                    score += 2
            if score > 0:
                scored.append((score, m))
        scored.sort(key=lambda x: (-x[0], x[1].command))
        return [m for _, m in scored[:limit]]

    def doc_stub(self, command: str) -> dict[str, Any] | None:
        m = self.get(command)
        if not m:
            return None
        props = (m.input_schema or {}).get("properties") or {}
        return {
            "command": m.command,
            "version": m.version,
            "description": m.description,
            "usage": f"gax {m.command} --repo owner/name",
            "required_scopes": m.required_scopes,
            "arguments": {
                k: {
                    "type": v.get("type", "string"),
                    "description": v.get("description", ""),
                    "required": k in ((m.input_schema or {}).get("required") or []),
                }
                for k, v in props.items()
            },
            "side_effects": m.side_effects,
        }
