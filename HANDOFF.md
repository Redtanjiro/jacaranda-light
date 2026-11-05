# Jacaranda Light — handoff

A single-page web app that tells amateur photographers **where and when** to shoot Sydney's jacarandas. It maps 2,645 jacarandas across greater Sydney (council inventories, OpenStreetMap and iNaturalist), groups them into 109 photo spots plus 5 hand-picked favourites, and scores every hour of the next 7 days from sun position, per-spot forecast weather, tree count and street direction. Forecast cloud drifts over the map.

Status: live at https://redtanjiro.github.io/jacaranda-light/ (GitHub Pages from `/docs` on `main`), also published as a Claude artifact.

---

## Repo layout

```
src/index.template.html     The whole app: HTML + CSS + JS. One placeholder: __DATA__ (trees)
data/trees.json             Trees + clustered spots (inlined as __DATA__)
data/basemap.json           Land, water, parks, main roads, rail, suburb labels (fetched on load)
data/tiles/r_<i>_<j>.json   Residential streets, 0.06° tiles, fetched once zoomed in
data/suburbs_wkt.json       Simplified suburb polygons inside the bounds, used to name spots
scripts/build.py            Inlines trees into the template, copies basemap + tiles → docs/
scripts/fetch_trees.py      Re-pulls council trees from ArcGIS and re-clusters them
scripts/fetch_extra_trees.py  Adds OSM + iNaturalist jacarandas and their spots to data/trees.json
scripts/extract_suburbs.py  NSW suburb GeoJSON → subs.pkl + data/suburbs_wkt.json
scripts/parse_osm.py        Step 1 of the basemap: NSW .osm.pbf → osm.pkl
scripts/build_basemap.py    Step 2 of the basemap: osm.pkl + subs.pkl → data/basemap.json + data/tiles/
docs/                       Built site: what GitHub Pages serves, and what gets published as the artifact
```

Build: `python3 scripts/build.py`. No bundler, no dependencies at runtime. The data scripts need `pip install shapely osmium requests`.

---

## Data

### Trees (`data/trees.json`)
```
{ trees: [[lat, lon, heightM, src], ...],      // src 0 = City of Sydney, 1 = Randwick, 2 = OpenStreetMap, 3 = iNaturalist
  spots: [{name, lat, lon, n, h, src, b, el}, ...] }
```
- `n` tree count, `h` average height, `b` street bearing 0–180° (principal axis of the cluster), `el` elongation (axis ratio; >1.8 means it's a real street run).
- Spots = DBSCAN-style clusters, eps 45 m, min 6 trees. City of Sydney spots are named by the suburb polygon they fall in; Randwick spots by their most common street.
- Extra spots (src 2/3) are looser clusters: eps 120 m, min 3 trees, named by suburb. OSM and iNaturalist trees within 8 m / 15 m of a council tree are dropped as duplicates.
- 5 hand-added "local favourites" live in the template (`FAV` array): Kirribilli McDougall St, Lavender Bay, USyd Quadrangle, Hunters Hill, Parramatta Park. These councils don't publish species data.

Sources (both public ArcGIS REST, queried with `upper(species) like '%JACARANDA%'`):
- City of Sydney Trees FeatureServer — 1,562 trees
- Randwick City Council Street_Tree FeatureServer — 494 trees
- Parramatta's "Greening Parramatta" layer was checked and dropped: its jacaranda rows are vacant planting sites.
- OpenStreetMap `natural=tree` nodes mentioning Jacaranda — 277 kept
- iNaturalist *Jacaranda mimosifolia* (taxon 77541), any grade (street trees are logged as cultivated, so few reach research grade), accuracy ≤ 100 m — 312 kept
- An ArcGIS Online search (Nov 2026) found no other Sydney council publishing tree species.

`fetch_extra_trees.py OSM_FILE` is re-runnable: it drops src ≥ 2 and rebuilds them.

`scripts/fetch_trees.py` rebuilds this file. **It has not been run end to end** (the original pull was done through a browser, because the build sandbox couldn't reach ArcGIS). Compare its output with the current file before trusting it.

### Basemap (`data/basemap.json` + `data/tiles/`)
```
{ b: bounds, land: [poly], water: [poly], green: [poly], roads: [[motorway/trunk],[primary],[secondary/tertiary]], rail: [line],
  sub: [[name, x, y, areaM2]], tile: {size: 0.06, keys: ["i_j", ...]} }
tiles/r_<i>_<j>.json: [line, ...]   residential/unclassified streets whose midpoint is in tile i,j (from the bounds' SW corner)
```
- Coordinates are delta-encoded ints: `x = (lon-151)*1e5`, `y = (lat+34)*1e5`, each pair stored as the difference from the previous point. A poly is `[outerRing, ...holes]`.
- Bounds: lon 150.62–151.35, lat -34.13 to -33.57 (Richmond/Penrith to the coast, Palm Beach to Campbelltown/Camden).
- Roads, parks, water, rail: the NSW OpenStreetMap extract from download.openstreetmap.fr (Oct–Nov 2026). Parks under ~2,000 m² are dropped.
- Land/shoreline: union of NSW suburb polygons from github.com/digitalpoetry/nsw-suburb-geojson (its `suburb/` folder holds 10 separate FeatureCollections).
- To rebuild: download the NSW `.osm.pbf`, clone the suburb repo, then run `extract_suburbs.py <repo>/suburb`, `parse_osm.py <nsw.osm.pbf>`, `build_basemap.py`, `fetch_extra_trees.py <nsw.osm.pbf>`, `build.py`. Total ~2 minutes.
- Size: basemap.json 3.3 MB (1.3 MB gzipped), tiles 2.1 MB across 124 files.

Attribution required in the footer: © OpenStreetMap contributors; also credited: iNaturalist, Open-Meteo, City of Sydney, Randwick.

---

## How the app works (all in `src/index.template.html`)

**Sun.** NOAA solar position algorithm (`sunPos`), computed per spot. `sunEvents` scans the day in 2-minute steps for sunrise, sunset and golden-hour edges (sun at 6°). Times are handled in `Australia/Sydney` via `Intl`, so DST is correct.

**Light score, 0–100 (`score(elev, w)`).**
- Base by sun height: golden hour (-1° to 6°) 96, low sun (6–15°) 74, blue hour (-6° to -1°) 58, then falling to 30 at high midday. Night is 0.
- Low sun: a low cloud deck cuts it; some high cloud (around 40%) adds colour.
- High sun: cloud acts as a softbox and pulls the score toward 82, because overcast light keeps purples saturated.
- Rain probability scales it down by up to 75%. Wind over 28 km/h takes off 10.

**Spot rank (`spotScore`).** `light × 0.78` plus up to 14 for tree count (10 for favourites), plus up to 9 when the sun is low (-1° to 15°) and lines up with the street bearing (`cos²` of the angle difference, weighted by elongation). Each row carries a plain-English reason. `rankSpots()` re-runs on every render for the selected day and hour.

**Bands, used for pins, list and log:** Skip <28, Fair <48, Good <68, Great <85, Go now ≥85. Colours: `#5b6390 #f08a7a #b49ce4 #58d68d #f7c98f`.

**Weather, in order of preference:**
1. AccuWeather through the Claude `mcp` capability (`window.claude.use("mcp")`, `watchTool` on `widgets-hourly-claude` for the next 12 h and `widgets-daily-claude` for the rest, Sydney CBD location key `3496594`). Only works inside the Claude artifact viewer for people with the connector.
2. Open-Meteo hourly (`tryLive`): one request for a 7 × 6 grid of points over the map (~11 km apart): cloud total/low/mid/high, rain probability, 10 m wind and 850 hPa wind. Works on GitHub Pages; blocked inside the artifact sandbox.
3. Manual sky preset per day (clear, some cloud, overcast, showers) in the Field Notes tab.

`weatherFor(day, hour, spot)` returns `{c, lo, hi, p, wind}` (cloud %, low cloud %, high cloud %, rain %, wind km/h) for that spot: bilinear from the grid when it's loaded, else the city-wide AccuWeather value, else the preset. So spots across Sydney can rank differently under the same hour.

**Live time.** `state.follow` is true by default: the page selects the current hour, ticks every 20 s, advances on the hour and rolls over at midnight. Outside 5am–8pm it jumps to the next 5am. Any manual day or hour change turns follow off; the NOW button turns it back on.

**Map.** Hand-rolled Canvas 2D at device pixel ratio. Equirectangular projection with `cos(33.9°)` x-scale. View state is `{cx, cy, z}`, clamped to the bounds. `Z0` is the inner-city zoom that thresholds are measured against; the first view fits every spot. Supports pointer drag, wheel and pinch zoom. Polylines are culled by bounding box; secondary/tertiary roads draw at ≥ 0.3× Z0, residential tiles load and draw at ≥ 0.7×. Zoomed out, only big centres are labelled (`TOWNS`).

**Map edge.** `drawFog` paints ten stacked, translucent bands outside ragged, noise-wobbled copies of the bounds, so the map dissolves into the screen colour instead of stopping at a straight line. It is skipped when the view is well inside the bounds.

**Clouds.** A third canvas between the map and the labels. A tileable noise texture (rank-equalised, so a threshold of 1 − cover fills that share of the area) is sampled per pixel on a ¼–⅕ resolution buffer, upscaled and CSS-blurred. Low+mid cover makes puffy cloud; high cover makes thin streaks along the wind. Coverage comes from the forecast grid for the selected hour; drift follows the 850 hPa wind at 45× real speed. Colour follows the sun (warm at golden hour, lavender at blue hour, dim at night), rain probability greys them, and when the sun is up they cast offset shadows. The ☁ button toggles them (remembered); reduced-motion stops the drift. The shapes are illustrative; only the amount and position follow the forecast. Trees are glow + core circles. Suburb labels sit on a second full-res canvas. Pins are DOM buttons positioned over the canvas: the top 20 ranked spots always show, the rest at 1.8× zoom, and the top 3 get number badges.

**UI.** The dock on the map is collapsible: Best Spots first, Field Notes second. Its open state is kept in `localStorage`, and it starts folded on phones. On phones (≤ 700 px) the page goes edge to edge: no desk margin or frame border, and the header, map and controls fill one screen, with the log below. Below the map: a day/time strip (Today, Tmrw, a dropdown for the rest, an LCD with ▲▼, NOW), then the 7-day × 16-hour forecast log.

---

## Known gaps and next steps

1. **AccuWeather path.** Still there behind feature detection for the artifact viewer. It is city-wide only; drop it if the artifact stops mattering.
2. **Coverage outside the two councils is thin.** OSM and iNaturalist only have trees people mapped or photographed (589 across the rest of Sydney). Crowd-sourced pins or council data requests would help most for North Sydney, Ku-ring-gai, Inner West, Hills.
3. **Forecast grid is ~11 km.** Clouds and per-spot weather are interpolated between grid points; Open-Meteo picks the model.
4. **Scoring is heuristic.** Weights were picked by judgement, not tested against real photos. Worth tuning with feedback.
5. **Bloom stage isn't modelled.** It assumes peak season (late Oct to mid Nov).
6. `fetch_trees.py` (council pull) still hasn't had a real run; the basemap and extra-tree scripts were run end to end on 5 Nov 2026.
7. Fonts load from Google Fonts (Silkscreen, Pixelify Sans, VT323) with monospace and system fallbacks.

## Design notes
- Pixel-handheld look: bevelled light-blue frame, navy map screen, chunky bordered buttons with inset shadows, green LCD readouts, speech-bubble field notes. It deliberately keeps one visual look on both light and dark hosts.
- The map itself is drawn smooth (not pixelated) at the user's request; everything around it keeps the pixel style.
- No Spider-Man or other licensed character art. The pins are original pixel jacaranda flowers.
