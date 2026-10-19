#!/bin/sh
# Full refresh: scrape Realtor.com -> process -> build the page. Safe to re-run;
# a same-day re-run only re-pulls counties that failed.
#   sh update.sh            # everything
#   sh update.sh --force    # re-pull every county even if already saved today
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
.venv/bin/python scrape.py "$@"
.venv/bin/python process.py
.venv/bin/python build_page.py
echo "done -> open texas-triangle-land.html"
