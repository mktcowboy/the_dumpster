/* Small geometry helpers (no dependencies). Coordinates are [lng, lat]. */
(function (g) {
  const R = 6371008.8, rad = d => d * Math.PI / 180;
  function dist(a, b) { // haversine meters
    const dLat = rad(b[1] - a[1]), dLng = rad(b[0] - a[0]);
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }
  function length(coords) { let s = 0; for (let i = 1; i < coords.length; i++) s += dist(coords[i - 1], coords[i]); return s; }
  function ringArea(ring) { // spherical excess approximation (same as Turf), m^2
    let a = 0; const n = ring.length; if (n < 3) return 0;
    for (let i = 0; i < n; i++) {
      const p1 = ring[i], p2 = ring[(i + 1) % n], p3 = ring[(i + 2) % n];
      a += (rad(p3[0]) - rad(p1[0])) * Math.sin(rad(p2[1]));
    }
    return Math.abs(a * R * R / 2);
  }
  function inRing(pt, ring) {
    let c = false; const [x, y] = pt;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) c = !c;
    }
    return c;
  }
  function inPolygon(pt, geom) {
    if (!geom) return false;
    const polys = geom.type === 'Polygon' ? [geom.coordinates] : geom.type === 'MultiPolygon' ? geom.coordinates : [];
    return polys.some(p => p && p[0] && p[0].length > 2 && inRing(pt, p[0]) && !p.slice(1).some(h => h && inRing(pt, h)));
  }
  function fmtDist(m) { const mi = m / 1609.344; return mi >= 0.2 ? `${mi.toFixed(2)} mi (${(m / 1000).toFixed(2)} km)` : `${Math.round(m * 3.28084)} ft (${Math.round(m)} m)`; }
  function fmtArea(m2) { const ac = m2 / 4046.8564; return ac >= 640 ? `${ac.toFixed(0)} ac (${(ac / 640).toFixed(2)} sq mi)` : `${ac.toFixed(2)} ac (${(m2 / 10000).toFixed(2)} ha)`; }
  function dms(v, pos, neg) { const s = v < 0 ? neg : pos; v = Math.abs(v); const d = Math.floor(v), mF = (v - d) * 60, m = Math.floor(mF), sec = ((mF - m) * 60).toFixed(1); return `${d}°${m}'${sec}"${s}`; }
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function toGPX(features) {
    const t = new Date().toISOString();
    let wpts = '', trks = '';
    for (const f of features) {
      const nm = esc(f.properties?.name || ''), desc = esc(f.properties?.notes || '');
      const g = f.geometry;
      if (g.type === 'Point') wpts += `  <wpt lat="${g.coordinates[1]}" lon="${g.coordinates[0]}"><name>${nm}</name>${desc ? `<desc>${desc}</desc>` : ''}</wpt>\n`;
      else {
        const pts = g.type === 'Polygon' ? g.coordinates[0] : g.coordinates;
        trks += `  <trk><name>${nm}</name>${desc ? `<desc>${desc}</desc>` : ''}<type>${g.type === 'Polygon' ? 'area' : 'line'}</type><trkseg>\n` +
          pts.map(c => `    <trkpt lat="${c[1]}" lon="${c[0]}"/>`).join('\n') + `\n  </trkseg></trk>\n`;
      }
    }
    return `<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Cleveland County Land Map" xmlns="http://www.topografix.com/GPX/1/1">\n  <metadata><time>${t}</time></metadata>\n${wpts}${trks}</gpx>\n`;
  }
  function fromGPX(text) {
    const doc = new DOMParser().parseFromString(text, 'application/xml'), out = [];
    const nm = el => el.querySelector(':scope > name')?.textContent || '';
    doc.querySelectorAll('wpt').forEach(w => out.push({ type: 'Feature', properties: { name: nm(w) }, geometry: { type: 'Point', coordinates: [+w.getAttribute('lon'), +w.getAttribute('lat')] } }));
    doc.querySelectorAll('trk, rte').forEach(t => {
      const pts = [...t.querySelectorAll('trkpt, rtept')].map(p => [+p.getAttribute('lon'), +p.getAttribute('lat')]);
      if (pts.length > 1) out.push({ type: 'Feature', properties: { name: nm(t) }, geometry: { type: 'LineString', coordinates: pts } });
    });
    return out;
  }
  g.Geo = { dist, length, ringArea, inPolygon, fmtDist, fmtArea, dms, esc, toGPX, fromGPX };
})(window);
