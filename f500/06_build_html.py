"""Assemble the single-file HTML: CSS + body + inlined JSON data + JS (CDN: D3, Leaflet, MarkerCluster, topojson-client)."""
import json, datetime
D = 'src/'
companies = json.load(open('data/companies.json')); edges = json.load(open('data/edges.json')); stats = json.load(open('data/stats.json'))
states = json.load(open('data/us-states.json'))
data = {'companies': companies, 'edges': edges, 'states': states, 'meta': {'year': 2026, 'built': datetime.date.today().strftime('%b %d, %Y'), 'stats': stats}}
js = ''.join(open(D + f'app{i}.js').read() + '\n' for i in range(1, 6))
html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fortune 500 · 2026 Atlas</title><meta name="description" content="Interactive atlas of the 2026 Fortune 500: profiles, map, industries and relationships.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"><link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">
<style>{open(D + 'style.css').read()}</style></head><body>
{open(D + 'body.html').read()}
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script src="https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js"></script>
<script>const DATA = {json.dumps(data, separators=(',', ':')).replace('</', '<\\/')};</script>
<script>{js}</script></body></html>'''
open('f500_explorer.html', 'w').write(html)
print('wrote', len(html) / 1e6, 'MB')
