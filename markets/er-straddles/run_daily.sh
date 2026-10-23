#!/bin/bash
# Afternoon pipeline (weekdays ~2:40 PM CT, before the close): N100 analysis + 'pm' straddle snapshot + crush + site.
set -e
cd "$(dirname "$0")" && . .venv/bin/activate && python batch.py && python build_site.py
