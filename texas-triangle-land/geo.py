import json, math, csv

# ---- triangle ----
# vertices: Dallas, San Antonio, Houston (metro centers)
V = [(32.7767,-96.7970),(29.4241,-98.4936),(29.7604,-95.3698)]  # (lat,lon)

def hav_mi(a,b):
    la1,lo1,la2,lo2 = map(math.radians,[a[0],a[1],b[0],b[1]])
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 3959*2*math.asin(math.sqrt(h))

def point_in_poly(pt, poly):
    x,y = pt[1],pt[0]; inside=False; n=len(poly)
    for i in range(n):
        x1,y1 = poly[i][1],poly[i][0]; x2,y2 = poly[(i+1)%n][1],poly[(i+1)%n][0]
        if ((y1>y)!=(y2>y)) and (x < (x2-x1)*(y-y1)/(y2-y1)+x1): inside = not inside
    return inside

def dist_pt_seg_mi(p,a,b):
    # equirectangular projection around p
    lat0 = math.radians(p[0])
    def proj(q): return ((q[1]-p[1])*math.cos(lat0)*69.0, (q[0]-p[0])*69.0)
    ax,ay = proj(a); bx,by = proj(b)
    dx,dy = bx-ax, by-ay
    t = 0 if dx==0 and dy==0 else max(0,min(1,-(ax*dx+ay*dy)/(dx*dx+dy*dy)))
    return math.hypot(ax+t*dx, ay+t*dy)

def dist_to_triangle_mi(p):
    if point_in_poly(p,V): return 0.0
    return min(dist_pt_seg_mi(p,V[i],V[(i+1)%3]) for i in range(3))

# ---- county rough centroids from us-atlas topojson ----
d = json.load(open('counties-10m.json'))
t = d['transform']; sx,sy = t['scale']; tx0,ty0 = t['translate']
arcs = d['arcs']
def decode(arc):
    x=y=0; pts=[]
    for dx,dy in arc:
        x+=dx; y+=dy; pts.append((x*sx+tx0, y*sy+ty0))  # lon,lat
    return pts
arc_cache = {}
def arc_pts(i):
    if i not in arc_cache: arc_cache[i]=decode(arcs[i if i>=0 else ~i])
    return arc_cache[i]
def geom_arcs(g):
    tp=g['type']
    if tp=='Polygon': polys=[g['arcs']]
    elif tp=='MultiPolygon': polys=g['arcs']
    else: return
    for poly in polys:
        for ring in poly:
            for ai in ring:
                pts = arc_pts(ai)
                yield pts if ai>=0 else pts[::-1]
centroids={}
for g in d['objects']['counties']['geometries']:
    if not g['id'].startswith('48'): continue
    xs=[];ys=[]
    for pts in geom_arcs(g):
        for x,y in pts: xs.append(x);ys.append(y)
    if xs: centroids[g['id']]=(sum(ys)/len(ys), sum(xs)/len(xs))

names={}
for row in csv.reader(open('national_county.txt')):
    if row[1]=='48': names['48'+row[2]]=row[3].replace(' County','')

print(f"{'county':18} {'lat':>7} {'lon':>8} {'d_tri_mi':>8}")
rows=[]
for fid,(la,lo) in sorted(centroids.items(), key=lambda kv: names.get(kv[0],kv[0])):
    dt = dist_to_triangle_mi((la,lo))
    rows.append((names.get(fid,fid),la,lo,dt))
for n,la,lo,dt in rows:
    if dt<=85: print(f"{n:18} {la:7.2f} {lo:8.2f} {dt:8.1f}")
print('total within 85mi:', sum(1 for r in rows if r[3]<=85))
json.dump([{'name':n,'lat':round(la,3),'lon':round(lo,3),'d_tri_mi':round(dt,1)} for n,la,lo,dt in rows if dt<=85],
          open('counties_near.json','w'), indent=1)
