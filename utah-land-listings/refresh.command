#!/bin/bash
# Double-click to refresh the Utah land listings and rebuild the map page.
cd "$(dirname "$0")"
/usr/bin/python3 refresh.py "$@"
echo; read -n 1 -s -r -p "Done. Press any key to close."
