#!/usr/bin/env python3
"""Build MASTER.md and master_rank.json for Best of 2024. Logic: scripts/bestof_master.py.

Usage: python3 build_master.py [MASTER.md]
"""
import runpy, sys
from pathlib import Path
sys.argv[1:1] = ['2024']
runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts' / 'bestof_master.py'), run_name='__main__')
