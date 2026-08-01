#!/usr/bin/env python3
"""
Copy bundled data into the package directory before building a wheel.

The repo keeps `manifests/`, `config/`, and `schemas/` at the project root
(`gax/manifests`, next to `gax/gax`) because that is where contributors expect
to edit them. Wheels need them *inside* the package (`gax/gax/manifests`) so
they survive installation and don't collide with other distributions at
site-packages root.

Rather than move the sources and disturb every existing path, this syncs them at
build time. `gax/paths.py` prefers the in-package copy and falls back to the repo
layout, so editable installs keep working from the originals.

    python sync_package_data.py        # before: python -m build

The copies are generated artifacts — add `gax/gax/{manifests,config,schemas}/`
to .gitignore rather than committing them.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "gax"
DATA_DIRS = ("manifests", "config", "schemas", "profiles")


def sync() -> int:
    copied = 0
    for name in DATA_DIRS:
        src = ROOT / name
        if not src.is_dir():
            print(f"  ! {name}/ not found at {src} — skipped")
            continue
        dst = PKG / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        n = sum(1 for _ in dst.rglob("*") if _.is_file())
        copied += n
        print(f"  ✓ {name}/ → gax/{name}/ ({n} files)")
    return copied


if __name__ == "__main__":
    print("Syncing package data for wheel build:")
    total = sync()
    if total == 0:
        print("No data files copied — wheel would be incomplete.", file=sys.stderr)
        sys.exit(1)
    print(f"Done ({total} files).")
