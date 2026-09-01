#!/usr/bin/env bash
# Start LangBot with local langbot-plugin patches applied.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SYNC=0
for arg in "$@"; do
  case "$arg" in
    --sync) SYNC=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [[ "$SYNC" -eq 1 ]]; then
  uv sync --dev
fi

uv run --no-sync python scripts/apply-langbot-plugin-patches.py

export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
export BOX__ENABLED="${BOX__ENABLED:-false}"

exec uv run --no-sync main.py
