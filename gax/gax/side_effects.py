"""
Side-effect ladder — the danger level of a command, and the ceiling a capability
is allowed to reach.

Every manifest declares `side_effects: read | write | destructive`. Every capability
carries a `max_side_effect` ceiling (default `read`). A capability may only invoke a
command whose level is at or below its ceiling.

**Why this exists as a second check.** The capability already carries an explicit
command allowlist, so in principle naming the command is enough. But an allowlist is
edited by humans under time pressure, and the failure mode is silent: add
`k8s.pod.delete` to a token that was meant to be read-only and nothing complains. The
ceiling makes that mistake inert — two independent things must be wrong before
something gets deleted, and the second one has to be stated in the explicit language
of danger rather than as an opaque command name.

Defaults fail closed:
  - a manifest with no/unknown `side_effects` is treated as `destructive`
  - a capability with no ceiling is treated as `read`

so a command added without thinking about danger is refused rather than allowed.
"""

from __future__ import annotations

from typing import Any

# Ordered least → most dangerous. Index is the comparison key.
LADDER: tuple[str, ...] = ("read", "write", "destructive")

DEFAULT_CEILING = "read"
# Unknown manifest levels fail closed at the top of the ladder.
UNKNOWN_LEVEL = "destructive"


def level_rank(level: str | None) -> int:
    """Rank of a side-effect level. Unknown/missing → most dangerous."""
    if not level:
        return LADDER.index(UNKNOWN_LEVEL)
    try:
        return LADDER.index(str(level).strip().lower())
    except ValueError:
        return LADDER.index(UNKNOWN_LEVEL)


def normalize(level: str | None) -> str:
    """Canonical level name, failing closed on anything unrecognized."""
    return LADDER[level_rank(level)]


def capability_ceiling(claims: dict[str, Any]) -> str:
    """
    The ceiling this capability may reach.

    Absent → `read`. A capability minted before ceilings existed therefore cannot
    invoke a destructive command, which is the safe direction for that migration.
    """
    return normalize(claims.get("max_side_effect") or DEFAULT_CEILING)


def exceeds_ceiling(claims: dict[str, Any], command_level: str | None) -> bool:
    """True when `command_level` is more dangerous than the capability allows."""
    return level_rank(command_level) > level_rank(capability_ceiling(claims))


def is_destructive(level: str | None) -> bool:
    return normalize(level) == "destructive"
