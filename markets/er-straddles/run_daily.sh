#!/bin/bash
# Refresh everything: N100 analysis + straddle snapshot + rebuild site. Suggested cron: 45 14 * * 1-5 (2:45pm CT, before close)
cd "$(dirname "$0")" && . .venv/bin/activate && python batch.py && python build_site.py
