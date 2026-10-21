#!/bin/bash
# Morning snapshot (weekdays ~9:00 AM CT, 30 min after the open): 'am' snapshot only for names whose earnings
# reaction is today (reported last night AMC / pre-market today), then recompute crush + rebuild site. ~1 min.
set -e
cd "$(dirname "$0")" && . .venv/bin/activate && python snapshot.py --session am --reporters-only && python build_site.py
