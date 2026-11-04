"""Fetch every council-listed jacaranda, cluster them into photo spots, and write data/trees.json.

NOTE: this script reproduces the pipeline that was originally run by hand (browser JS + one-off
Python). It has not been run end to end in this form, so check the output against the current
data/trees.json (2,056 trees, 74 spots) the first time.

Requires: pip install requests shapely
Sources:
  City of Sydney  https://services1.arcgis.com/cNVyNtjGVZybOQWZ/arcgis/rest/services/Trees/FeatureServer/0
  Randwick        https://mapservices.randwick.nsw.gov.au/arcgis/rest/services/Hosted/Street_Tree/FeatureServer/0
"""
import json, math, re
from collections import Counter, defaultdict
from pathlib import Path
import requests
from shapely import wkt
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    dict(src=0, url="https://services1.arcgis.com/cNVyNtjGVZybOQWZ/arcgis/rest/services/Trees/FeatureServer/0/query",
         where="upper(SpeciesName) like '%JACARANDA%'", fields="TreeHeight", h="TreeHeight", street=None),
    dict(src=1, url="https://mapservices.randwick.nsw.gov.au/arcgis/rest/services/Hosted/Street_Tree/FeatureServer/0/query",
         where="upper(species) like '%JACARANDA%'", fields="suburb,address,totaltreeh", h="totaltreeh", street="address"),
]

def fetch(s):
    out, offset = [], 0
    while True:
        r = requests.get(s["url"], params=dict(where=s["where"], outFields=s["fields"], outSR=4326, returnGeometry="true",
                                               resultOffset=offset, resultRecordCount=2000, f="json"), timeout=60).json()
        feats = r.get("features", [])
        for f in feats:
            a, g = f["attributes"], f["geometry"]
            street = None
            if s["street"]:
                st = re.sub(r"^[\d\-/A-Za-z]*\d[\dA-Za-z\-/]*\s+", "", a.get(s["street"]) or "")
                st = re.sub(r"\s+(NSW \d{4} AU|New South Wales \d{4} Australia|Sydney NSW \d{4} AU)$", "", st).strip()
                street = (st.title(), (a.get("suburb") or "").title())
            out.append(dict(lat=round(g["y"], 5), lon=round(g["x"], 5), h=a.get(s["h"]) or 0, src=s["src"], st=street))
        if not r.get("exceededTransferLimit"): break
        offset += len(feats)
    return out

trees = [t for s in SOURCES for t in fetch(s)]
print("trees", len(trees), Counter(t["src"] for t in trees))

# --- DBSCAN-style clustering: eps 45 m, min 6 trees
dist = lambda a, b: math.hypot((a["lat"]-b["lat"])*111000, (a["lon"]-b["lon"])*92500)
EPS, MINP = 45, 6
grid = defaultdict(list)
cell = lambda t: (int(t["lat"]*111000//EPS), int(t["lon"]*92500//EPS))
for i, t in enumerate(trees): grid[cell(t)].append(i)
def nb(i):
    k = cell(trees[i]); return [j for dx in (-1,0,1) for dy in (-1,0,1) for j in grid[(k[0]+dx, k[1]+dy)] if dist(trees[i], trees[j]) <= EPS]
lab = [-1]*len(trees); cid = 0
for i in range(len(trees)):
    if lab[i] != -1: continue
    N = nb(i)
    if len(N) < MINP: lab[i] = -2; continue
    lab[i] = cid; q = list(N)
    while q:
        j = q.pop()
        if lab[j] == -2: lab[j] = cid
        if lab[j] != -1: continue
        lab[j] = cid; M = nb(j)
        if len(M) >= MINP: q += M
    cid += 1

subs = [(n, wkt.loads(w)) for n, w in json.loads((ROOT/"data/suburbs_wkt.json").read_text())]
def suburb(lat, lon):
    p = Point(lon, lat); return next((n for n, g in subs if g.contains(p)), "Sydney")

spots = []
for c in range(cid):
    m = [t for t, l in zip(trees, lab) if l == c]
    la = sum(t["lat"] for t in m)/len(m); lo = sum(t["lon"] for t in m)/len(m)
    if m[0]["src"] == 1:
        st = Counter(t["st"] for t in m).most_common(1)[0][0]; name = f"{st[0]}, {st[1]}"
    else:
        name = suburb(la, lo)
    # street direction from the shape of the cluster (principal axis), plus elongation
    pts = [((t["lon"]-lo)*92500, (t["lat"]-la)*111000) for t in m]
    sxx = sum(x*x for x, y in pts); syy = sum(y*y for x, y in pts); sxy = sum(x*y for x, y in pts)
    ang = 0.5*math.atan2(2*sxy, sxx-syy); tr = sxx+syy; det = sxx*syy-sxy*sxy
    l1 = tr/2+math.sqrt(max(0, tr*tr/4-det)); l2 = max(1e-6, tr/2-math.sqrt(max(0, tr*tr/4-det)))
    spots.append(dict(name=name, lat=round(la, 5), lon=round(lo, 5), n=len(m), h=round(sum(t["h"] for t in m)/len(m)),
                      src=m[0]["src"], b=round((90-math.degrees(ang)) % 180), el=round(min(9, math.sqrt(l1/l2)), 1)))
spots.sort(key=lambda s: -s["n"])
tot = Counter(s["name"] for s in spots); seen = Counter()
for s in spots:
    if tot[s["name"]] > 1: seen[s["name"]] += 1; s["name"] = f'{s["name"]} #{seen[s["name"]]}'

out = dict(trees=[[round(t["lat"], 4), round(t["lon"], 4), t["h"], t["src"]] for t in trees], spots=spots)
(ROOT/"data/trees.json").write_text(json.dumps(out, separators=(",", ":")))
print("spots", len(spots))
