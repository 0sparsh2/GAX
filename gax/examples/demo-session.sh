#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true

echo "=== GAX demo session ==="

gaxd start --background 2>/dev/null || true
sleep 1

export GAX_CAP="$(gax auth cap-mint \
  --command demo.echo \
  --command gh.pr.list \
  --scope demo:echo \
  --scope github:pull_request:read \
  --ttl 3600)"

echo "--- search ---"
gax search "echo"

echo "--- doc ---"
gax doc demo.echo

echo "--- demo.echo ---"
gax demo.echo --message "from demo-session.sh"

echo "--- gh.pr.list (mock if gh missing) ---"
gax gh.pr.list --repo octocat/Hello-World --surface model

echo "--- audit tail ---"
tail -n 3 ~/.gax/audit.jsonl 2>/dev/null || echo "(no audit yet)"
