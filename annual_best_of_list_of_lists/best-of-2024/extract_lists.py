#!/usr/bin/env python3
"""Write items.json for Best of 2024. Logic: scripts/bestof_extract.py; site parsers: custom.py.

Usage: python3 extract_lists.py [lists.csv] [cache_dir]
"""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts' / 'bestof_extract.py'), run_name='__main__')
