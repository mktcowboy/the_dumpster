import json, math, csv
from geo import V, hav_mi, point_in_poly, dist_to_triangle_mi  # noqa

d = json.load(open('counties-10m.json'))
t = d['transform']; sx,sy = t['scale']; tx0,ty0 = t['translate']
arcs = d['arcs']
def decode(arc):
    x=y=0; pts=[]
    for dx,dy in arc:
        x+=dx; y+=dy; pts.append((y*sy+ty0, x*sx+tx0))  # lat,lon
    return pts
arc_cache={}
def arc_pts(i):
    if i not in arc_cache: arc_cache[i]=decode(arcs[i if i>=0 else ~i])
    return arc_cache[i]

def county_rings(g):
    tp=g['type']
    polys=[g['arcs']] if tp=='Polygon' else g['arcs']
    for poly in polys:
        for ring in poly:
            pts=[]
            for ai in ring:
                p=arc_pts(ai); pts += p if ai>=0 else p[::-1]
            yield pts

names={}
for row in csv.reader(open('national_county.txt')):
    if row[1]=='48': names['48'+row[2]]=row[3].replace(' County','')

def seg_dist(p,a,b):
    lat0=math.radians(p[0])
    kx=math.cos(lat0)*69.0; ky=69.0
    ax,ay=(a[1]-p[1])*kx,(a[0]-p[0])*ky; bx,by=(b[1]-p[1])*kx,(b[0]-p[0])*ky
    dx,dy=bx-ax,by-ay
    t=0 if dx==0 and dy==0 else max(0,min(1,-(ax*dx+ay*dy)/(dx*dx+dy*dy)))
    return math.hypot(ax+t*dx,ay+t*dy)

results=[]
for g in d['objects']['counties']['geometries']:
    if not g['id'].startswith('48'): continue
    name=names.get(g['id'],g['id'])
    rings=list(county_rings(g))
    # min distance from county boundary points to triangle
    mind=min(dist_to_triangle_mi(pt) for ring in rings for pt in ring[::7])
    # triangle vertex inside county? (cheap bbox precheck then ray cast on outer ring)
    inside=False
    outer=max(rings,key=len)
    for v in V:
        if point_in_poly(v,outer): inside=True;break
    if inside: mind=0.0
    results.append((name,mind))
results.sort(key=lambda r:r[1])
inside=[r for r in results if r[1]<=52]
print(f"counties with any land within ~52mi of triangle: {len(inside)}")
for n,dd in inside: print(f"  {n:16} {dd:5.1f}")
json.dump([n for n,_ in inside], open('counties_target.json','w'))
