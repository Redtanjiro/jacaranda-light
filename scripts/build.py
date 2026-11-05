"""Build the site into docs/ (served by GitHub Pages from /docs, and published as the Claude artifact).

Usage:  python3 scripts/build.py
Writes: docs/index.html     the page, with data/trees.json inlined as __DATA__
        docs/basemap.json   core basemap layers, fetched by the page on load
        docs/tiles/*.json   residential streets, fetched per tile once you zoom in
        docs/og.png         link-preview image (from scripts/make_og_image.py)
"""
import shutil
from pathlib import Path
from urllib.parse import quote

root = Path(__file__).resolve().parent.parent
tpl = (root / "src/index.template.html").read_text()
trees = (root / "data/trees.json").read_text()
body = tpl.replace("__DATA__", trees)
# link-preview scrapers only read <title> from <head>, so lift it out of the template body
title = body[body.index("<title>"):body.index("</title>")+8]
body = body.replace(title + "\n", "", 1)

# favicon: the same pixel flower as the title plate (FLOWER/FMAP in the template)
FLOWER = ["..p.p..", ".ppppp.", "ppPyPpp", ".pyyyp.", "ppPyPpp", ".ppppp.", "..p.p.."]
FMAP = {"p": "#c3a1ff", "P": "#8b5cf6", "y": "#f7e27a"}
rects = "".join(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{FMAP[c]}"/>' for y, row in enumerate(FLOWER) for x, c in enumerate(row) if c in FMAP)
icon = "data:image/svg+xml," + quote(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 7 7" shape-rendering="crispEdges">{rects}</svg>')

# what link previews (WhatsApp, iMessage, Slack...) show when the site is shared
URL = "https://redtanjiro.github.io/jacaranda-light/"
DESC = "Jacaranda season is here. Get your perfect pictures with Jacaranda Bae."

# GitHub Pages serves the file as-is, so it needs its own document skeleton
head = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
{title}
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#5bb8ec">
<link rel="icon" type="image/svg+xml" href="{icon}">
<meta name="description" content="{DESC}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Jacaranda Bae">
<meta property="og:title" content="Jacaranda Bae">
<meta property="og:description" content="{DESC}">
<meta property="og:url" content="{URL}">
<meta property="og:image" content="{URL}og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Jacaranda Bae pixel title over a night map of Sydney with pixel clouds">
<meta name="twitter:card" content="summary_large_image">
</head>
<body>
"""
docs = root / "docs"
docs.mkdir(exist_ok=True)
(docs / "index.html").write_text(head + body + "\n</body>\n</html>\n")
(docs / ".nojekyll").write_text("")
shutil.copy(root / "data/basemap.json", docs / "basemap.json")
shutil.copy(root / "data/og.png", docs / "og.png")
shutil.rmtree(docs / "tiles", ignore_errors=True)
shutil.copytree(root / "data/tiles", docs / "tiles")
n = len(list((docs / "tiles").glob("*.json")))
size = sum(f.stat().st_size for f in docs.rglob("*") if f.is_file())
print(f"docs/index.html {(docs / 'index.html').stat().st_size/1024:.0f} KB · basemap.json {(docs / 'basemap.json').stat().st_size/1e6:.2f} MB · {n} tiles · {size/1e6:.2f} MB total")
