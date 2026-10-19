"""Triangle geometry shared by every step: vertices, point-in-polygon, distance to edge."""
import math

# Triangle vertices (lat, lon): Dallas, San Antonio, Houston (metro centers)
V = [(32.7767, -96.7970), (29.4241, -98.4936), (29.7604, -95.3698)]
BUFFER_MI = 50.0


def point_in_poly(pt, poly):
    x, y = pt[1], pt[0]
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][1], poly[i][0]
        x2, y2 = poly[(i + 1) % n][1], poly[(i + 1) % n][0]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
            inside = not inside
    return inside


def dist_pt_seg_mi(p, a, b):
    """Miles from p to segment ab (equirectangular projection around p)."""
    lat0 = math.radians(p[0])
    kx = math.cos(lat0) * 69.0
    ax, ay = (a[1] - p[1]) * kx, (a[0] - p[0]) * 69.0
    bx, by = (b[1] - p[1]) * kx, (b[0] - p[0]) * 69.0
    dx, dy = bx - ax, by - ay
    t = 0 if dx == 0 and dy == 0 else max(0, min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx, ay + t * dy)


def dist_to_triangle_mi(p):
    """0 inside the triangle, otherwise miles to the nearest edge."""
    if point_in_poly(p, V):
        return 0.0
    return min(dist_pt_seg_mi(p, V[i], V[(i + 1) % 3]) for i in range(3))


def zone_of(lat, lon):
    """('inside' | 'buffer' | 'outside', miles to triangle)."""
    d = dist_to_triangle_mi((lat, lon))
    if d == 0.0:
        return "inside", d
    return ("buffer" if d <= BUFFER_MI else "outside"), d
