#!/bin/bash
# Weekly entry point for GitHub Actions (and any local scheduler).
#
# Saved listings in saved/<slug>/ are reused while they are inside the
# freshness window (default 2 days, saved/freshness.json or PATEK_FRESH_DAYS).
# Pass --force to scrape again anyway.
set -euo pipefail

cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
exec "${PYTHON:-python3}" "./refresh_searches_v2.py" "$@"
