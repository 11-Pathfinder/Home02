# London Schools Catchment Mapper

## Architecture
- **Python pipeline**: `fetch_data.py` → `process_data.py` → `generate_map.py` (Folium, secondary)
- **Primary map**: `output/london_schools_maplibre_v02_dotdensity.html` (MapLibre GL JS, all inline)
- **Published** via GitHub Pages from `docs/index.html`
- **Station data**: `fetch_stations.py` fetches from TfL API → `data/stations.json`
- School + station data embedded as JS constants (`SCHOOLS_DATA`, `STATIONS_DATA`) in the HTML

## File sync rule
After any edit to the map HTML, always sync all three copies:
```
output/london_schools_maplibre_v02_dotdensity.html  (primary, edit this)
output/london_schools_maplibre.html                  (copy)
docs/index.html                                      (GitHub Pages)
```

## Key decisions
- MapLibre GL JS over Folium for interactivity and WebGL performance
- Canvas-drawn station icons (not SVG/images) — MapLibre silently drops entire symbol layers if `text-font` references a font not in the glyph server
- National Rail icon uses official SVG path data rendered via Path2D
- Independent/private schools labelled "Independent" (brown #8B4513), not "Not yet inspected"
- School dot colors chosen to contrast with CartoDB Positron basemap (no green/blue)
- Invisible hit-target layer (3x radius mobile, 1.8x desktop) behind school dots for tap accessibility
- school-points layer moved above station-icons for click priority

## Data
- ~2,055 schools (1,758 state + 297 private), ~546 religious
- 710 stations (tube, DLR, overground, Elizabeth line, national rail)
- GIAS for school establishments, Ofsted MI for ratings
- Private schools identified via `EstablishmentTypeGroup = "Independent schools"` + age range filter

## Rating colors (MapLibre)
- Outstanding: `#e8456b` (rose/coral)
- Good: `#757575` (dark grey)
- Requires improvement: `#c8a800` (dark yellow)
- Inadequate: `#1a1a1a` (black)
- New framework: `#7b1fa2` (deep purple)
- Not yet inspected: `#1b3a6b` (navy blue)
- Independent: `#8B4513` (brown)

## Toggles
- Show Stations (default: on)
- Show Private Schools (default: off)
- Show Religious Schools (default: on)

## Deployment
- GitHub repo: `11-Pathfinder/Home02`
- Branch: `claude/plan-schools-catchment-mapper-HUUWE`
- GitHub Pages serves from `/docs` on that branch
- Live at: https://11-pathfinder.github.io/Home02/
