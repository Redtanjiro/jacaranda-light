"""Build the site into docs/ (served by GitHub Pages from /docs, and published as the Claude artifact).

Usage:  python3 scripts/build.py
Writes: docs/index.html     the page, with data/trees.json inlined as __DATA__
        docs/basemap.json   core basemap layers, fetched by the page on load
        docs/tiles/*.json   residential streets, fetched per tile once you zoom in
"""
import shutil
from pathlib import Path
from urllib.parse import quote

root = Path(__file__).resolve().parent.parent
tpl = (root / "src/index.template.html").read_text()
trees = (root / "data/trees.json").read_text()
body = tpl.replace("__DATA__", trees)

# favicon: the same pixel flower as the title plate (FLOWER/FMAP in the template)
FLOWER = ["..p.p..", ".ppppp.", "ppPyPpp", ".pyyyp.", "ppPyPpp", ".ppppp.", "..p.p.."]
FMAP = {"p": "#c3a1ff", "P": "#8b5cf6", "y": "#f7e27a"}
rects = "".join(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{FMAP[c]}"/>' for y, row in enumerate(FLOWER) for x, c in enumerate(row) if c in FMAP)
icon = "data:image/svg+xml," + quote(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 7 7" shape-rendering="crispEdges">{rects}</svg>')

# GitHub Pages serves the file as-is, so it needs its own document skeleton
head = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#5bb8ec">
<link rel="icon" type="image/svg+xml" href="{icon}">
<meta name="description" content="Where and when to photograph Sydney's jacarandas: council-listed, mapped and sighted trees across Sydney, grouped into photo spots and scored hour by hour from sun, forecast cloud and street direction.">
</head>
<body>
"""
docs = root / "docs"
docs.mkdir(exist_ok=True)
(docs / "index.html").write_text(head + body + "\n</body>\n</html>\n")
(docs / ".nojekyll").write_text("")
shutil.copy(root / "data/basemap.json", docs / "basemap.json")
shutil.rmtree(docs / "tiles", ignore_errors=True)
shutil.copytree(root / "data/tiles", docs / "tiles")
n = len(list((docs / "tiles").glob("*.json")))
size = sum(f.stat().st_size for f in docs.rglob("*") if f.is_file())
print(f"docs/index.html {(docs / 'index.html').stat().st_size/1024:.0f} KB · basemap.json {(docs / 'basemap.json').stat().st_size/1e6:.2f} MB · {n} tiles · {size/1e6:.2f} MB total")
