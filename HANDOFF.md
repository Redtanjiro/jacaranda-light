# Jacaranda Light — handoff

A single-page web app that tells amateur photographers **where and when** to shoot Sydney's jacarandas. It maps 2,056 council-listed trees, groups them into 74 photo spots, and scores every hour of the next 7 days from sun position, weather, tree count and street direction.

Status: working prototype, published as a Claude artifact. Next step is to host it as a normal website (e.g. GitHub Pages) so live weather works for everyone.

---

## Repo layout

```
src/index.template.html   The whole app: HTML + CSS + JS. Has two placeholders: __DATA__ and __BASE__
data/trees.json           Trees + clustered spots (inlined as __DATA__)
data/basemap.json         Land, water, parks, roads, rail, suburb labels (inlined as __BASE__)
data/suburbs_wkt.json     Simplified NSW suburb polygons, used to name spots
scripts/build.py          Inlines the two JSON files into the template → dist/ and docs/
scripts/fetch_trees.py    Re-pulls trees from council ArcGIS services and re-clusters them
scripts/parse_osm.py      Step 1 of the basemap: OSM XML → osm.pkl
scripts/build_basemap.py  Step 2 of the basemap: osm.pkl + subs.pkl → data/basemap.json
dist/index.html           Built page without doctype/head, for the Claude artifact (host adds the skeleton)
docs/index.html           Same page with doctype, charset and viewport, served by GitHub Pages from /docs
```

Build: `python3 scripts/build.py`. No bundler, no dependencies at runtime.

---

## Data

### Trees (`data/trees.json`)
```
{ trees: [[lat, lon, heightM, src], ...],      // src 0 = City of Sydney, 1 = Randwick
  spots: [{name, lat, lon, n, h, src, b, el}, ...] }
```
- `n` tree count, `h` average height, `b` street bearing 0–180° (principal axis of the cluster), `el` elongation (axis ratio; >1.8 means it's a real street run).
- Spots = DBSCAN-style clusters, eps 45 m, min 6 trees. City of Sydney spots are named by the suburb polygon they fall in; Randwick spots by their most common street.
- 5 hand-added "local favourites" live in the template (`FAV` array): Kirribilli McDougall St, Lavender Bay, USyd Quadrangle, Hunters Hill, Parramatta Park. These councils don't publish species data.

Sources (both public ArcGIS REST, queried with `upper(species) like '%JACARANDA%'`):
- City of Sydney Trees FeatureServer — 1,562 trees
- Randwick City Council Street_Tree FeatureServer — 494 trees
- Parramatta's "Greening Parramatta" layer was checked and dropped: its jacaranda rows are vacant planting sites.

`scripts/fetch_trees.py` rebuilds this file. **It has not been run end to end** (the original pull was done through a browser, because the build sandbox couldn't reach ArcGIS). Compare its output with the current file before trusting it.

### Basemap (`data/basemap.json`)
```
{ b: bounds, land: [poly], water: [poly], green: [poly], roads: [[motorway/trunk],[primary],[secondary/tertiary],[residential]], rail: [line], sub: [[name, x, y, areaM2]] }
```
- Coordinates are delta-encoded ints: `x = (lon-151)*1e5`, `y = (lat+34)*1e5`, each pair stored as the difference from the previous point. A poly is `[outerRing, ...holes]`.
- Roads, parks, rail: OpenStreetMap extract `sydney.osm` (2017) from github.com/illi4/Sydney_osm. Bounds: lon 151.079–151.296, lat -34.005 to -33.823 (inner city, east, lower north shore; Parramatta is off-map).
- Land/shoreline: union of NSW suburb polygons from github.com/digitalpoetry/nsw-suburb-geojson. The OSM extract's coastline is missing Sydney Harbour, so the suburb union is what draws the harbour.
- To rebuild: clone both repos, run `parse_osm.py` to get `osm.pkl`, extract suburbs inside the bounds to `subs.pkl` (filter `enddate` starting `3000`), then run `build_basemap.py`. Needs shapely.

Attribution required in the footer: © OpenStreetMap contributors.

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
2. Open-Meteo hourly (`tryLive`), fetched directly. Blocked inside the artifact sandbox; should work on a normal host. Not yet tested on one.
3. Manual sky preset per day (clear, some cloud, overcast, showers) in the Field Notes tab.

`weatherFor(day, hour)` returns `{c, lo, hi, p, wind}`, meaning cloud %, low cloud %, high cloud %, rain % and wind km/h, from whichever source is loaded.

**Live time.** `state.follow` is true by default: the page selects the current hour, ticks every 20 s, advances on the hour and rolls over at midnight. Outside 5am–8pm it jumps to the next 5am. Any manual day or hour change turns follow off; the NOW button turns it back on.

**Map.** Hand-rolled Canvas 2D at device pixel ratio. Equirectangular projection with `cos(33.9°)` x-scale. View state is `{cx, cy, z}`. Supports pointer drag, wheel and pinch zoom. Polylines are culled by bounding box, residential roads only draw at zoom ≥ 0.7× fit. Trees are glow + core circles. Suburb labels sit on a second full-res canvas. Pins are DOM buttons positioned over the canvas: the top 20 ranked spots always show, the rest at 1.8× zoom, and the top 3 get number badges.

**UI.** The dock on the map is collapsible: Best Spots first, Field Notes second. Its open state is kept in `localStorage`, and it starts folded on phones. Below the map: a day/time strip (Today, Tmrw, a dropdown for the rest, an LCD with ▲▼, NOW), then the 7-day × 16-hour forecast log.

---

## Known gaps and next steps

1. **Host outside Claude** (GitHub Pages) so Open-Meteo loads for everyone. Then decide whether to drop the AccuWeather path or keep it behind feature detection, as it is now.
2. **Weather is city-wide.** Both feeds use one Sydney point, so every spot gets the same weather. Per-spot weather would only matter for far-apart spots.
3. **Coverage.** Only City of Sydney and Randwick publish species. North Sydney, Ku-ring-gai, Inner West etc. need another source: crowd-sourced pins, iNaturalist observations, or council data requests.
4. **Basemap is 2017 OSM** and stops at the bounds above. Swapping to a hosted vector tile source (e.g. Protomaps PMTiles) would remove the 670 KB inline basemap and cover all of Sydney, once the page lives somewhere that can load it.
5. **Scoring is heuristic.** Weights were picked by judgement, not tested against real photos. Worth tuning with feedback.
6. **Bloom stage isn't modelled.** It assumes peak season (late Oct to mid Nov).
7. `fetch_trees.py` and the basemap scripts need a first real run to confirm they reproduce the current data.
8. Fonts load from Google Fonts (Silkscreen, Pixelify Sans, VT323) with monospace and system fallbacks.

## Design notes
- Pixel-handheld look: bevelled light-blue frame, navy map screen, chunky bordered buttons with inset shadows, green LCD readouts, speech-bubble field notes. It deliberately keeps one visual look on both light and dark hosts.
- The map itself is drawn smooth (not pixelated) at the user's request; everything around it keeps the pixel style.
- No Spider-Man or other licensed character art. The pins are original pixel jacaranda flowers.
