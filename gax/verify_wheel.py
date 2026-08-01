#!/usr/bin/env python3
"""
Verify a built wheel is complete before it can be published.

This exists because we shipped this bug once already: the wheel carried no
`config/policy.yaml`, so a `pip install`ed GAX loaded an *empty* policy and every
tenant allowlist silently disappeared. Nothing failed loudly — commands just ran
without the rules that were supposed to constrain them.

That class of bug is invisible from a repo checkout (`pip install -e .` reads the
sources directly) and only appears on a clean install. A PyPI release is permanent:
you can yank a version but never reuse the number. So the build fails here rather
than discovering it after publishing.

    python verify_wheel.py dist/gax-0.4.0-py3-none-any.whl
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

# Data that must be inside the package. Losing any of these produces an install
# that looks fine and behaves wrong.
REQUIRED_FILES = [
    "gax/config/policy.yaml",  # tenant allowlists + destructive kill switch
    "gax/config/oauth_providers.yaml",
    "gax/schemas/envelope.v1.json",
]

REQUIRED_PREFIXES = {
    "gax/manifests/": 5,  # registered commands
    "gax/profiles/": 8,  # bundled command sets
}

# Shipping these at wheel root collides with other distributions in site-packages.
FORBIDDEN_PREFIXES = ("manifests/", "config/", "schemas/", "profiles/", "tests/")

REQUIRED_MODULES = [
    "gax/cli.py",
    "gax/daemon.py",
    "gax/mcp_server.py",
    "gax/executor.py",
    "gax/policy.py",
    "gax/side_effects.py",
    "gax/profiles.py",
    "gax/onboarding.py",
]


def verify(wheel: Path) -> list[str]:
    names = set(zipfile.ZipFile(wheel).namelist())
    problems: list[str] = []

    for required in REQUIRED_FILES + REQUIRED_MODULES:
        if required not in names:
            problems.append(f"missing {required}")

    for prefix, minimum in REQUIRED_PREFIXES.items():
        found = sum(1 for n in names if n.startswith(prefix) and n.endswith(".yaml"))
        if found < minimum:
            problems.append(
                f"only {found} file(s) under {prefix}, expected >= {minimum} "
                "(did you run sync_package_data.py?)"
            )

    for name in sorted(names):
        if name.startswith(FORBIDDEN_PREFIXES):
            problems.append(f"data at wheel root would collide: {name}")

    return problems


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    wheels = [Path(a) for a in sys.argv[1:]]
    wheels = [w for w in wheels if w.suffix == ".whl"]
    if not wheels:
        print("no .whl given", file=sys.stderr)
        return 2

    failed = False
    for wheel in wheels:
        problems = verify(wheel)
        if problems:
            failed = True
            print(f"\n  ✗ {wheel.name} is incomplete:\n", file=sys.stderr)
            for p in problems:
                print(f"      - {p}", file=sys.stderr)
        else:
            n = len(zipfile.ZipFile(wheel).namelist())
            print(f"  ✓ {wheel.name} complete ({n} files)")

    if failed:
        print(
            "\n  Do NOT publish. Run: python sync_package_data.py && python -m build\n",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
