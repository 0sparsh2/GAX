#!/usr/bin/env bash
# Publish eval/results/live-run-summary.md as a public GitHub gist (requires gh auth).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FILE="${ROOT}/eval/results/live-run-summary.md"
if [[ ! -f "$FILE" ]]; then
  echo "Missing $FILE — run: python eval/run_comparison.py --live-mcp" >&2
  exit 1
fi
gh gist create "$FILE" --public --desc "GAX vs CLI vs MCP — live eval summary (tiktoken, 18 tasks)"
