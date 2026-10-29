#!/bin/bash
# Weekly entry point for GitHub Actions and the UPDATE button.
#
# Run from boy-toy-pricer/aircraft (this script cds to its own directory).
# Saved listings in saved/sr22/, saved/sf50/, saved/cubcrafters/, and
# saved/pa28-180-181/ are reused while they are inside the freshness window
# (default 2 days, saved/freshness.json or SR22_FRESH_DAYS). Pass --force to
# scrape again anyway. A source that fails keeps its last good file.
set -euo pipefail

cd "$(dirname "$0")"
# Prefer the project venv so launchd and the UPDATE button use the same
# interpreter that installed Playwright. GitHub Actions has no .venv.
if [ -z "${PYTHON:-}" ] && [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi
export PYTHONUNBUFFERED=1
exec "${PYTHON:-python3}" "./refresh_searches.py" "$@"
