"""
Profiles — bundled sets of ready-to-use commands.

The adoption problem this solves: GAX shipped 11 commands, mostly mocks, so a new
user's first task was authoring YAML for everything they actually cared about.
A framework that ships empty doesn't get adopted.

A profile is a directory of manifests under `gax/profiles/<name>/`. Installing one
copies them into `~/.gax/manifests/`, which the registry loads *after* the packaged
set — so profile commands survive package upgrades and can be edited in place.

Profiles deliberately span the danger ladder (`read` → `write` → `destructive`).
A profile of only read commands would make the side-effect ceiling untestable in
practice, and the ceiling is the thing worth demonstrating.

Installing a profile **grants nothing**. It registers commands; invoking them still
requires a capability naming the command, holding the scope, and reaching the
ceiling. `gax init --profile k8s` still hands out a read-only capability.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from gax.paths import PROFILES_DIR, USER_MANIFESTS_DIR


@dataclass
class ProfileCommand:
    command: str
    description: str
    side_effects: str
    required_scopes: list[str] = field(default_factory=list)


@dataclass
class Profile:
    name: str
    path: Path
    commands: list[ProfileCommand]

    @property
    def scopes(self) -> list[str]:
        seen: list[str] = []
        for c in self.commands:
            for s in c.required_scopes:
                if s not in seen:
                    seen.append(s)
        return sorted(seen)

    def by_level(self, level: str) -> list[ProfileCommand]:
        return [c for c in self.commands if c.side_effects == level]

    @property
    def summary(self) -> str:
        parts = [
            f"{len(self.by_level(lvl))} {lvl}"
            for lvl in ("read", "write", "destructive")
            if self.by_level(lvl)
        ]
        return ", ".join(parts)


def _read_profile(directory: Path) -> Profile:
    commands: list[ProfileCommand] = []
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        if not data.get("command"):
            continue
        commands.append(
            ProfileCommand(
                command=str(data["command"]),
                description=str(data.get("description", "")),
                side_effects=str(data.get("side_effects", "destructive")),
                required_scopes=list(data.get("required_scopes") or []),
            )
        )
    return Profile(name=directory.name, path=directory, commands=commands)


def available_profiles() -> dict[str, Profile]:
    if not PROFILES_DIR.exists():
        return {}
    return {
        d.name: _read_profile(d)
        for d in sorted(PROFILES_DIR.iterdir())
        if d.is_dir() and not d.name.startswith(("_", "."))
    }


def get_profile(name: str) -> Profile | None:
    return available_profiles().get(name)


def installed_commands() -> set[str]:
    """Commands currently present in the user manifests directory."""
    out: set[str] = set()
    if not USER_MANIFESTS_DIR.exists():
        return out
    for path in USER_MANIFESTS_DIR.glob("*.yaml"):
        data = yaml.safe_load(path.read_text()) or {}
        if data.get("command"):
            out.add(str(data["command"]))
    return out


def install_profile(name: str, *, force: bool = False) -> dict[str, Any]:
    """
    Copy a profile's manifests into `~/.gax/manifests/`.

    Existing files are skipped unless `force`, so a locally edited command is never
    silently overwritten by a reinstall.
    """
    profile = get_profile(name)
    if profile is None:
        raise KeyError(name)

    USER_MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    skipped: list[str] = []

    for src in sorted(profile.path.glob("*.yaml")):
        dst = USER_MANIFESTS_DIR / src.name
        if dst.exists() and not force:
            skipped.append(src.stem)
            continue
        shutil.copy2(src, dst)
        installed.append(src.stem)

    return {
        "profile": name,
        "installed": installed,
        "skipped": skipped,
        "target": str(USER_MANIFESTS_DIR),
        "scopes": profile.scopes,
        "commands": [c.command for c in profile.commands],
        "summary": profile.summary,
    }
