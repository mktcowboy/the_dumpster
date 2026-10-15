#!/usr/bin/env python3
"""Build the combined, standalone S&P 500 tracker from local sources."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def main():
    events = json.loads((ROOT / 'changes_20yr.json').read_text())
    removed = json.loads((ROOT / 'removed_list.json').read_text())
    prices = json.loads((ROOT / 'prices.json').read_text())
    spy = json.loads((ROOT / 'spy_monthly.json').read_text())
    assert events and spy, 'Change and benchmark data are required.'
    assert {r['ticker'] for r in removed} <= set(prices), 'Price cache must include every removal (including unavailable records).'
    payload = json.dumps({'events': events, 'removed': removed, 'prices': prices, 'spy': spy},
                         separators=(',', ':')).replace('<', '\\u003c')
    page = (ROOT / 'template.html').read_text()
    page = page.replace('/*__STYLES__*/', (ROOT / 'styles.css').read_text())
    page = page.replace('/*__DATA__*/', 'const DATA = ' + payload + ';')
    page = page.replace('/*__APP__*/', (ROOT / 'app.js').read_text())
    ids = re.findall(r'\bid="([^"]+)"', page.split('<script>')[0])
    assert len(ids) == len(set(ids)), 'Duplicate element IDs.'
    assert not re.search(r'<script[^>]+src=', page), 'Standalone page must embed all scripts.'
    (ROOT / 'index.html').write_text(page)
    print(f'Built index.html: {len(events)} change events, {len(removed)} removed tickers; all assets embedded.')


if __name__ == '__main__':
    main()
