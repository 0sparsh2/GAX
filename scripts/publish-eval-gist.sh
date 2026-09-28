#!/usr/bin/env bash
# Publish eval/results/live-run-summary.md to the public eval gist (requires gh auth).
#
# Updates the existing gist in place so every link in the repo keeps pointing at
# current numbers; GitHub keeps prior versions in the gist's revision history.
# Creating a new gist instead would leave the linked one showing stale results.
#
#   scripts/publish-eval-gist.sh           # update the linked gist
#   scripts/publish-eval-gist.sh --new     # create a separate new gist
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FILE="${ROOT}/eval/results/live-run-summary.md"
GIST_ID="${GAX_EVAL_GIST_ID:-cea07652091fc4d47637e87d958ed340}"
DESC="GAX vs CLI vs MCP — live eval summary (tokens, enforcement, command selection)"

if [[ ! -f "$FILE" ]]; then
  echo "Missing $FILE — run: python eval/run_comparison.py --live-mcp" >&2
  exit 1
fi

if [[ "${1:-}" == "--new" ]]; then
  gh gist create "$FILE" --public --desc "$DESC"
  exit 0
fi

# PATCH via the API rather than `gh gist edit`, which can fall back to an
# interactive editor. Replaces only live-run-summary.md; other files are kept.
BODY="$(mktemp)"
trap 'rm -f "$BODY"' EXIT
python3 -c 'import json,sys; print(json.dumps({"description": sys.argv[2], "files": {"live-run-summary.md": {"content": open(sys.argv[1]).read()}}}))' \
  "$FILE" "$DESC" > "$BODY"
gh api --method PATCH "gists/${GIST_ID}" --input "$BODY" \
  -q '"Updated \(.html_url) · revision \(.history[0].version[:7]) · \(.updated_at)"'
