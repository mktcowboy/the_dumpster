import html, math
e = html.escape
PAL = ["#0072B2","#E69F00","#009E73","#CC79A7","#56B4E9","#D55E00","#F0E442","#999999"]  # Okabe-Ito
def hbar(title, items, color="#0072B2", unit="", w=640, rowh=26, labw=230, fmt=lambda v: str(v)):
    mx = max(v for _, v in items) or 1
    h = 40 + rowh*len(items) + 10
    plot = w - labw - 70
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px;display:block" role="img" aria-label="{e(title)}" xmlns="http://www.w3.org/2000/svg" font-family="system-ui,Segoe UI,Arial" font-size="12">',
           f'<title>{e(title)}</title><text x="0" y="18" font-size="14" font-weight="700" fill="#1d2330">{e(title)}</text>']
    for i, (lab, v) in enumerate(items):
        y = 34 + i*rowh
        bw = plot * v / mx
        c = color[i % len(color)] if isinstance(color, list) else color
        out.append(f'<text x="{labw-8}" y="{y+rowh/2+4}" text-anchor="end" fill="#1d2330">{e(lab)}</text>'
                   f'<rect x="{labw}" y="{y+4}" width="{bw:.1f}" height="{rowh-9}" rx="3" fill="{c}"/>'
                   f'<text x="{labw+bw+6:.1f}" y="{y+rowh/2+4}" fill="#1d2330">{e(fmt(v))}{e(unit)}</text>')
    out.append('</svg>'); return ''.join(out)

def stacked(title, items, keys, colors, w=640, rowh=28, labw=170):
    # items: [(label, {key: val})]
    mx = max(sum(d.values()) for _, d in items) or 1
    h = 60 + rowh*len(items)
    plot = w - labw - 40
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px;display:block" role="img" aria-label="{e(title)}" xmlns="http://www.w3.org/2000/svg" font-family="system-ui,Segoe UI,Arial" font-size="12">',
           f'<title>{e(title)}</title><text x="0" y="18" font-size="14" font-weight="700" fill="#1d2330">{e(title)}</text>']
    lx = labw
    for k, c in zip(keys, colors):
        out.append(f'<rect x="{lx}" y="27" width="12" height="12" fill="{c}"/><text x="{lx+16}" y="37" fill="#1d2330">{e(k)}</text>'); lx += 16 + 8*len(k) + 20
    for i, (lab, d) in enumerate(items):
        y = 48 + i*rowh; x = labw
        out.append(f'<text x="{labw-8}" y="{y+rowh/2+4}" text-anchor="end" fill="#1d2330">{e(lab)}</text>')
        for k, c in zip(keys, colors):
            v = d.get(k, 0)
            if not v: continue
            bw = plot * v / mx
            out.append(f'<rect x="{x:.1f}" y="{y+4}" width="{bw:.1f}" height="{rowh-9}" fill="{c}"><title>{e(lab)}: {e(k)} {v}</title></rect>')
            if bw > 14: out.append(f'<text x="{x+bw/2:.1f}" y="{y+rowh/2+4}" text-anchor="middle" fill="#fff" font-weight="700">{v}</text>')
            x += bw
    out.append('</svg>'); return ''.join(out)

def logbar(title, items, w=700, rowh=26, labw=300, lo=-3, hi=2):
    # items: [(label, value_mg_per_kg, color, group)]
    h = 76 + rowh*len(items)
    plot = w - labw - 60
    X = lambda v: labw + plot * (math.log10(v) - lo) / (hi - lo)
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px;display:block" role="img" aria-label="{e(title)}" xmlns="http://www.w3.org/2000/svg" font-family="system-ui,Segoe UI,Arial" font-size="12">',
           f'<title>{e(title)}</title><text x="0" y="18" font-size="14" font-weight="700" fill="#1d2330">{e(title)}</text>']
    for p in range(lo, hi+1):
        x = X(10**p)
        out.append(f'<line x1="{x:.1f}" y1="30" x2="{x:.1f}" y2="{h-38}" stroke="#d5d9e0" stroke-dasharray="3 3"/><text x="{x:.1f}" y="{h-24}" text-anchor="middle" fill="#5d6678">{10**p:g}</text>')
    for i, (lab, v, c, g) in enumerate(items):
        y = 32 + i*rowh
        out.append(f'<text x="{labw-8}" y="{y+rowh/2+4}" text-anchor="end" fill="#1d2330">{e(lab)}</text>'
                   f'<rect x="{labw}" y="{y+4}" width="{X(v)-labw:.1f}" height="{rowh-9}" rx="3" fill="{c}"><title>{e(lab)}: {v:g} mg/kg</title></rect>'
                   f'<text x="{X(v)+5:.1f}" y="{y+rowh/2+4}" fill="#1d2330">{v:g}</text>')
    out.append(f'<text x="{labw+plot/2:.1f}" y="{h-6}" text-anchor="middle" fill="#5d6678" font-size="11">mg/kg (log scale)</text></svg>')
    return ''.join(out)
