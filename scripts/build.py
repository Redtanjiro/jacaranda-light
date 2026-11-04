"""Inline tree + basemap data into the page template.

Usage:  python3 scripts/build.py
Writes: dist/index.html  body-only page for the Claude artifact (host adds the skeleton)
        docs/index.html  standalone page for GitHub Pages (doctype, charset, viewport)
"""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
tpl = (root / "src/index.template.html").read_text()
trees = (root / "data/trees.json").read_text()
base = (root / "data/basemap.json").read_text()

out = tpl.replace("__DATA__", trees).replace("__BASE__", base)
(root / "dist").mkdir(exist_ok=True)
(root / "dist/index.html").write_text(out)
print(f"dist/index.html  {len(out)/1024:.0f} KB")

# GitHub Pages serves the file as-is, so it needs its own document skeleton
head = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#15131c">
<meta name="description" content="Where and when to photograph Sydney's jacarandas: 2,056 council-listed trees, 74 photo spots, scored hour by hour from sun, weather and street direction.">
</head>
<body>
"""
site = head + out + "\n</body>\n</html>\n"
(root / "docs").mkdir(exist_ok=True)
(root / "docs/index.html").write_text(site)
(root / "docs/.nojekyll").write_text("")
print(f"docs/index.html  {len(site)/1024:.0f} KB")
