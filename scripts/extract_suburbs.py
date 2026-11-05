"""Pull current NSW suburb polygons inside the basemap bounds.

Usage:  python3 scripts/extract_suburbs.py PATH/TO/nsw-suburb-geojson/suburb
        (git clone https://github.com/digitalpoetry/nsw-suburb-geojson)
Writes: subs.pkl              [(properties, shapely geometry)], input for build_basemap.py
        data/suburbs_wkt.json [[name, simplified WKT]], used to name spots
Requires: pip install shapely
"""
import json, pickle, sys
from pathlib import Path
from shapely.geometry import shape, box

ROOT = Path(__file__).resolve().parent.parent
B = box(150.62, -34.13, 151.35, -33.57).buffer(0.02)
subs = []
for f in sorted(Path(sys.argv[1]).glob("*.geojson")):  # each part is its own FeatureCollection
    for ft in json.loads(f.read_text())["features"]:
        p = ft["properties"]
        if not str(p.get("enddate", "")).startswith("3000"): continue  # retired boundaries
        g = shape(ft["geometry"])
        if g.intersects(B): subs.append((p, g.buffer(0)))
pickle.dump(subs, open(ROOT/"subs.pkl", "wb"))
(ROOT/"data/suburbs_wkt.json").write_text(json.dumps([[p["suburbname"].title(), g.simplify(0.0001).wkt] for p, g in subs]))
print("suburbs", len(subs))
