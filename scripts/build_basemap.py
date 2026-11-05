"""Step 2 of the basemap: osm.pkl + subs.pkl -> data/basemap.json + data/tiles/*.json

Usage:  python3 scripts/build_basemap.py   (after parse_osm.py and extract_suburbs.py)
Coordinates are delta-encoded ints: x = (lon-151)*1e5, y = (lat+34)*1e5. A poly is [outerRing, ...holes].
basemap.json holds everything drawn at every zoom (land, water, parks, main roads, rail, suburb labels).
Residential streets are split into TILE-degree tiles (data/tiles/r_<i>_<j>.json, each a list of lines)
that the page fetches only once you zoom in far enough to draw them.
Requires: pip install shapely
"""
import json, math, pickle
from collections import defaultdict
from pathlib import Path
from shapely import wkb
from shapely.geometry import LineString, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
B = (150.62, -34.13, 151.35, -33.57); bb = box(*B)
TILE = 0.06
osm = pickle.load(open(ROOT/"osm.pkl", "rb"))
subs = pickle.load(open(ROOT/"subs.pkl", "rb"))

def q(x, y): return [round((x-151)*1e5), round((y+34)*1e5)]
def enc(cs):
    out = []; px = py = 0
    for x, y in cs:
        X, Y = q(x, y); out += [X-px, Y-py]; px, py = X, Y
    return out
def polys(g, minA=2e-8):
    gs = list(g.geoms) if hasattr(g, "geoms") else [g]; res = []
    for p in gs:
        if p.geom_type != "Polygon" or p.area < minA: continue
        res.append([enc(p.exterior.coords)] + [enc(i.coords) for i in p.interiors if abs(LineString(i.coords).envelope.area) > minA])
    return res

# land: union of suburb polygons (the OSM coastline is unreliable inside the harbour)
landU = unary_union([g for p, g in subs]).buffer(0.00002).buffer(-0.00002).intersection(bb.buffer(0.03)).simplify(0.00004)
SUBS = []
for p, g in subs:
    if g.area < 2e-6: continue
    c = g.representative_point()
    if bb.contains(c): SUBS.append([p["suburbname"].title(), *q(c.x, c.y), round(g.area*1e6)])

green, water = [], []
for kind, w in osm["areas"].values():
    g = wkb.loads(w)
    if g.is_empty or g.area < 4e-8 or not g.intersects(bb): continue
    (green if kind == "green" else water).append(g.buffer(0))
G = polys(unary_union(green).intersection(landU).simplify(0.00004), 2e-7)  # skip parks under ~2,000 m²
WA = polys(unary_union(water).simplify(0.00004))

CLS = {"motorway": 0, "trunk": 0, "motorway_link": 0, "trunk_link": 0, "primary": 1, "primary_link": 1, "secondary": 2,
       "secondary_link": 2, "tertiary": 2, "tertiary_link": 2, "residential": 3, "unclassified": 3, "living_street": 3, "pedestrian": 3}
roads = [[], [], []]; tiles = defaultdict(list); rail = []
for t, cs in osm["lines"].values():
    l = LineString(cs)
    if not l.intersects(bb): continue
    if t.get("railway") == "rail": rail.append(enc(l.simplify(0.00003).coords)); continue
    c = CLS.get(t.get("highway"))
    if c is None: continue
    l = l.simplify(0.00003 if c < 3 else 0.000025)
    if c < 3: roads[c].append(enc(l.coords)); continue
    m = l.interpolate(0.5, normalized=True)
    tiles[(int((m.x-B[0])//TILE), int((m.y-B[1])//TILE))].append(enc(l.coords))

(ROOT/"data/tiles").mkdir(exist_ok=True)
for f in (ROOT/"data/tiles").glob("*.json"): f.unlink()
tsize = 0
for (i, j), ls in tiles.items():
    s = json.dumps(ls, separators=(",", ":")); tsize += len(s)
    (ROOT/f"data/tiles/r_{i}_{j}.json").write_text(s)
out = dict(sub=SUBS, b=[q(B[0], B[1]), q(B[2], B[3])], land=polys(landU), green=G, water=WA, roads=roads, rail=rail,
           tile=dict(size=TILE, keys=sorted(f"{i}_{j}" for i, j in tiles)))
s = json.dumps(out, separators=(",", ":")); (ROOT/"data/basemap.json").write_text(s)
print(f"basemap.json {len(s)/1e6:.2f} MB  tiles {len(tiles)} files {tsize/1e6:.2f} MB")
print("roads", [len(r) for r in roads], "green", len(G), "water", len(WA), "land", len(out["land"]), "subs", len(SUBS))
for k in ("land", "green", "water", "roads", "rail", "sub"): print(k, f"{len(json.dumps(out[k], separators=(',', ':')))/1e6:.2f} MB")
