#!/usr/bin/env python3
"""Cache monthly Yahoo closes for the tickers in the local change log."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent


def fetch(ticker):
    params = urlencode({'interval': '1mo', 'range': '20y'})
    symbol = quote(ticker.replace('.', '-'), safe='')
    for attempt in range(3):
        try:
            req = Request(f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{params}',
                          headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=25) as response:
                result = json.load(response)['chart']['result'][0]
            closes = result['indicators']['quote'][0]['close']
            points = {}
            for stamp, close in zip(result.get('timestamp', []), closes):
                if close is not None and close > 0:
                    day = datetime.fromtimestamp(stamp, timezone.utc).date().isoformat()
                    points[day[:7]] = [day, round(close, 4)]
            return ticker, {'px': list(points.values()),
                            'fetched': datetime.now(timezone.utc).date().isoformat(),
                            'source': 'Yahoo Finance', 'status': 'available'}
        except HTTPError as error:
            if error.code == 404:
                return ticker, {'px': [], 'status': 'unavailable'}
            if attempt == 2:
                return ticker, {'px': [], 'status': 'fetch failed'}
        except (OSError, KeyError, TypeError, ValueError, IndexError):
            if attempt == 2:
                return ticker, {'px': [], 'status': 'fetch failed'}
        time.sleep(1 + attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='also refresh cached histories')
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    events = json.loads((ROOT / 'changes_20yr.json').read_text())
    tickers = {e[k] for e in events for k in ('added_t', 'removed_t') if e[k]}
    destination = ROOT / 'prices.json'
    cache = json.loads(destination.read_text()) if destination.exists() else {}
    spy = json.loads((ROOT / 'spy_monthly.json').read_text())
    cache.setdefault('SPY', {'px': [[p['d'], p['c']] for p in spy],
                             'fetched': '2026-10-14', 'source': 'Yahoo Finance', 'status': 'available'})
    targets = sorted(tickers | {'SPY'}) if args.refresh else sorted(tickers - {t for t, r in cache.items() if r.get('px')})
    failures = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(fetch, t) for t in targets]
        for i, future in enumerate(as_completed(futures), 1):
            ticker, record = future.result()
            if record['px'] or not cache.get(ticker, {}).get('px'):
                cache[ticker] = record
            failures += record['status'] == 'fetch failed'
            if i % 50 == 0 or i == len(targets):
                destination.write_text(json.dumps(cache, separators=(',', ':')) + '\n')
                print(f'Fetched {i}/{len(targets)}; request failures: {failures}', flush=True)
            if i == 12 and failures == 12:
                raise RuntimeError('Price requests failed. Check network access and retry; existing histories are preserved.')
    destination.write_text(json.dumps(cache, separators=(',', ':')) + '\n')
    print(f'Cached {sum(bool(r.get("px")) for r in cache.values())} price histories; unavailable tickers remain visible.')


if __name__ == '__main__':
    main()
