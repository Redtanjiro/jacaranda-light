"""Step 1 of the basemap: OSM files -> osm.pkl (roads, rail, park and water areas).

Usage:  python3 scripts/parse_osm.py new_south_wales-latest.osm.pbf [more.osm.pbf ...]
Input:  the NSW extract from https://download.openstreetmap.fr/extracts/oceania/australia/ (~300 MB).
        Only features touching the basemap bounds (Penrith to the coast, Palm Beach to Campbelltown) are kept.
        If several files are given, ways that appear in more than one are kept once.
Writes: osm.pkl  {"lines": {id: (tags, [(lon, lat), ...])}, "areas": {id: (kind, wkb)}}
Requires: pip install osmium shapely
"""
import pickle, sys
from collections import Counter
import osmium
from shapely import wkb as swkb

ROAD = {"motorway", "trunk", "primary", "secondary", "tertiary", "motorway_link", "trunk_link", "primary_link",
        "secondary_link", "tertiary_link", "residential", "unclassified", "living_street", "pedestrian"}
GREEN = lambda t: (t.get("leisure") in ("park", "golf_course", "nature_reserve", "garden", "pitch")
                   or t.get("landuse") in ("grass", "recreation_ground", "cemetery", "forest")
                   or t.get("natural") in ("wood", "scrub"))
WATER = lambda t: t.get("natural") == "water" or t.get("waterway") == "riverbank" or t.get("water") is not None
B = (150.60, -34.15, 151.37, -33.55)  # basemap bounds plus a small margin
inb = lambda x, y: B[0] <= x <= B[2] and B[1] <= y <= B[3]
lines, areas = {}, {}
fab = osmium.geom.WKBFactory()

class H(osmium.SimpleHandler):
    def way(self, w):
        t = w.tags
        keep = t.get("highway") in ROAD or (t.get("railway") == "rail" and t.get("tunnel") is None)
        if not keep: return
        try: cs = [(n.lon, n.lat) for n in w.nodes if n.location.valid()]
        except osmium.InvalidLocationError: return
        if len(cs) < 2 or not any(inb(x, y) for x, y in cs[::4] + cs[-1:]): return
        if w.id in lines and len(lines[w.id][1]) >= len(cs): return  # same way clipped in another file
        lines[w.id] = ({k: t.get(k) for k in ("highway", "railway") if t.get(k)}, cs)
    def area(self, a):
        t = a.tags
        kind = "water" if WATER(t) else "green" if GREEN(t) else None
        if not kind: return
        try:
            if not any(inb(n.lon, n.lat) for r in a.outer_rings() for n in list(r)[::8]): return
            g = fab.create_multipolygon(a)
        except Exception: return
        if a.id not in areas or len(g) > len(areas[a.id][1]): areas[a.id] = (kind, bytes.fromhex(g) if isinstance(g, str) else g)

for p in sys.argv[1:]:
    H().apply_file(p, locations=True)
    print(p, "lines", len(lines), "areas", len(areas))
pickle.dump(dict(lines=lines, areas=areas), open("osm.pkl", "wb"))
print(Counter(t.get("highway") or t.get("railway") for t, _ in lines.values()).most_common(20))
print(Counter(k for k, _ in areas.values()))
