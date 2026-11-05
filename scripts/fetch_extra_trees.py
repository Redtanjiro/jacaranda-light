"""Add jacarandas from outside the two council inventories, and cluster them into extra photo spots.

Usage:  python3 scripts/fetch_extra_trees.py OSM_FILE [OSM_FILE ...]
Reads:  data/trees.json (council trees + spots from fetch_trees.py), data/suburbs_wkt.json, the OSM files
Writes: data/trees.json with the extra trees appended (src 2 = OpenStreetMap, 3 = iNaturalist) and extra spots

Sources:
  OpenStreetMap  natural=tree nodes whose species/genus/taxon/name mentions Jacaranda
  iNaturalist    Jacaranda mimosifolia (taxon 77541) observations, any grade (street trees are logged as
                 cultivated, so most never reach research grade), positional accuracy <= 100 m, not obscured
Neither is a full inventory: they are trees people have mapped or photographed, so spots are looser
(eps 120 m, min 3 trees) than the council clusters.

Requires: pip install requests shapely osmium
Re-running is safe: trees and spots with src >= 2 are dropped and rebuilt each time.
"""
import json, math, re, sys, time
from collections import defaultdict
from pathlib import Path
import requests, osmium
from shapely import wkt
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
BOUNDS = (150.62, -34.13, 151.35, -33.57)  # lon/lat box the basemap covers
UA = {"User-Agent": "JacarandaBae/1.0 (github.com/Redtanjiro/jacaranda-light)"}

def osm_trees(paths):
    out, seen = [], set()
    class H(osmium.SimpleHandler):
        def node(self, o):
            t = o.tags
            if t.get("natural") != "tree" or o.id in seen: return
            s = " ".join(t.get(k, "") for k in ("species", "genus", "taxon", "taxon:species", "species:en", "name"))
            if not re.search("jacaranda", s, re.I): return
            seen.add(o.id)
            try: h = float(re.sub(r"[^\d.]", "", t.get("height", "")) or 0)
            except ValueError: h = 0
            out.append(dict(lat=o.location.lat, lon=o.location.lon, h=round(h), src=2))
    for p in paths: H().apply_file(p)
    return out

def inat_trees():
    out, last = [], 0
    while True:
        r = requests.get("https://api.inaturalist.org/v1/observations", headers=UA, timeout=60, params=dict(
            taxon_id=77541, swlng=BOUNDS[0], swlat=BOUNDS[1], nelng=BOUNDS[2], nelat=BOUNDS[3], acc_below=101,
            geoprivacy="open", per_page=200, order_by="id", order="asc", id_above=last)).json()
        res = r.get("results", [])
        for o in res:
            if o.get("obscured") or not o.get("location"): continue
            la, lo = map(float, o["location"].split(","))
            out.append(dict(lat=la, lon=lo, h=0, src=3))
        if len(res) < 200: break
        last = res[-1]["id"]; time.sleep(1)
    return out

dist = lambda a, b: math.hypot((a["lat"]-b["lat"])*111000, (a["lon"]-b["lon"])*92500)

def dedupe(pts, against, r):
    """Drop points within r metres of any point in `against` or of a point already kept."""
    grid = defaultdict(list); cell = lambda p: (int(p["lat"]*111000//r), int(p["lon"]*92500//r))
    for p in against: grid[cell(p)].append(p)
    kept = []
    for p in pts:
        k = cell(p)
        if any(dist(p, q) <= r for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q in grid[(k[0]+dx, k[1]+dy)]): continue
        kept.append(p); grid[k].append(p)
    return kept

def cluster(trees, eps, minp):
    grid = defaultdict(list); cell = lambda t: (int(t["lat"]*111000//eps), int(t["lon"]*92500//eps))
    for i, t in enumerate(trees): grid[cell(t)].append(i)
    def nb(i):
        k = cell(trees[i]); return [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in grid[(k[0]+dx, k[1]+dy)] if dist(trees[i], trees[j]) <= eps]
    lab = [-1]*len(trees); cid = 0
    for i in range(len(trees)):
        if lab[i] != -1: continue
        N = nb(i)
        if len(N) < minp: lab[i] = -2; continue
        lab[i] = cid; q = list(N)
        while q:
            j = q.pop()
            if lab[j] == -2: lab[j] = cid
            if lab[j] != -1: continue
            lab[j] = cid; M = nb(j)
            if len(M) >= minp: q += M
        cid += 1
    return [[t for t, l in zip(trees, lab) if l == c] for c in range(cid)]

data = json.loads((ROOT/"data/trees.json").read_text())
council = [dict(lat=t[0], lon=t[1], h=t[2], src=t[3]) for t in data["trees"] if t[3] < 2]
inb = lambda t: BOUNDS[0] <= t["lon"] <= BOUNDS[2] and BOUNDS[1] <= t["lat"] <= BOUNDS[3]
o = [t for t in osm_trees(sys.argv[1:]) if inb(t)]
n = [t for t in inat_trees() if inb(t)]
print("osm", len(o), "inat", len(n))
# OSM first (exact positions), then iNat; a sighting within 15 m of a known tree is the same tree
extra = dedupe(o, council, 8)
extra += dedupe(n, council + extra, 15)
print("extra trees kept", len(extra), "osm", sum(t["src"] == 2 for t in extra), "inat", sum(t["src"] == 3 for t in extra))

subs = [(nm, wkt.loads(w)) for nm, w in json.loads((ROOT/"data/suburbs_wkt.json").read_text())]
def suburb(lat, lon):
    p = Point(lon, lat); return next((nm for nm, g in subs if g.contains(p)), "Sydney")

spots = [s for s in data["spots"] if s["src"] < 2]
names = {s["name"] for s in spots}
new = []
for m in cluster(extra, 120, 3):
    la = sum(t["lat"] for t in m)/len(m); lo = sum(t["lon"] for t in m)/len(m)
    pts = [((t["lon"]-lo)*92500, (t["lat"]-la)*111000) for t in m]
    sxx = sum(x*x for x, y in pts); syy = sum(y*y for x, y in pts); sxy = sum(x*y for x, y in pts)
    ang = 0.5*math.atan2(2*sxy, sxx-syy); tr = sxx+syy; det = sxx*syy-sxy*sxy
    l1 = tr/2+math.sqrt(max(0, tr*tr/4-det)); l2 = max(1e-6, tr/2-math.sqrt(max(0, tr*tr/4-det)))
    hs = [t["h"] for t in m if t["h"]]
    new.append(dict(name=suburb(la, lo), lat=round(la, 5), lon=round(lo, 5), n=len(m), h=round(sum(hs)/len(hs)) if hs else 0,
                    src=max(set(t["src"] for t in m), key=[t["src"] for t in m].count),
                    b=round((90-math.degrees(ang)) % 180), el=round(min(9, math.sqrt(l1/l2)), 1)))
new.sort(key=lambda s: -s["n"])
for s in new:
    base, k = s["name"], 1
    while s["name"] in names: k += 1; s["name"] = f"{base} #{k}"
    names.add(s["name"])
print("extra spots", len(new), [s["name"] for s in new[:12]])

trees = [[round(t["lat"], 4), round(t["lon"], 4), t["h"], t["src"]] for t in council + extra]
(ROOT/"data/trees.json").write_text(json.dumps(dict(trees=trees, spots=spots + new), separators=(",", ":")))
print("trees", len(trees), "spots", len(spots) + len(new))
