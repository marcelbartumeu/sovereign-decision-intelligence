# CLAUDE.md — Andorra V1.9

## Project overview
Interactive scenario modeling dashboard for Andorra, combining a React/Vite main app with an embedded ABM (agent-based model) visualization. Deployed on Vercel; also runs locally.

## Running locally
```bash
cd "Front end/dashboard"
npm install
npm run dev          # → http://localhost:5173 (or 5174/5175 if busy)
```
No build step needed — the viz app dist is pre-committed.

## Repo structure
```
Front end/
  dashboard/               ← Main Vite/React app (root dir for Vercel)
    src/
      components/          ← Map views, KPI cards, overlays
      pages/               ← Tab pages
      utils/               ← Data helpers, chart utils
    public/
      model/               ← GeoJSON data (bus, accessibility, population)
      Public/              ← Scenario images (overgrowth.png etc, Andorra1.jpg)
      growth_*.geojson     ← Growth scenario polygons
      tourism_*.geojson    ← Tourism layers
    viz-abm-emotion-main/  ← Standalone ABM viz (pre-built dist committed)
      src/pages/MapView.tsx          ← deck.gl agent map
      src/pages/AgentAnalyticsView.tsx
      src/services/SharedStateContext.tsx  ← loads 2302 agent JSON files
    vercel.json            ← Build: copies viz dist → public/andorra/, then vite build
    vite.config.js         ← Dev middleware: serves /andorra/* from viz dist
  Public/                  ← Scenario images source
  model/                   ← GeoJSON source files
Arduino/                   ← Hardware controller (Web Serial API)
conf/scenarios/            ← Scenario parameter JSON files
```

## Key architecture decisions
- **Viz app is an iframe** at `/andorra/` — loaded by MapVisualization.jsx for the "agents" layer
- **Vercel build**: `mkdir -p public/andorra && cp -r viz-abm-emotion-main/dist/. public/andorra/ && npm run build`
- **Vercel root dir**: must be set to `Front end/dashboard` in Vercel dashboard
- **Agent data**: 2302 JSON files loaded in parallel batches of 50 via `import.meta.glob`
- **Black mask**: SVG overlay outside the 4 keystone projection corners, applied to all map views and the viz app — defined in `src/components/MapMask.jsx`

## Map views
| Layer | Component | Notes |
|-------|-----------|-------|
| Base | BaseMapView.jsx | Esri satellite |
| Growth | GrowthMapView.jsx | Fetches `growth_*.geojson` |
| Tourism | TourismMapView.jsx | Ski, peaks, refuges, trails |
| Accessibility | AccessibilityMapView.jsx | Bus animation, hex grid |
| Population | PopulationMapView.jsx | H3 hex density |
| Agents (iframe) | viz-abm-emotion-main | deck.gl, served at /andorra/ |

## Projection corners (all maps must use these)
```
NW: [42.694543, 1.393847]
NE: [42.697242, 1.801074]
SE: [42.396861, 1.803713]
SW: [42.394176, 1.39849]
```
Leaflet maps: use `MapMask` component (`src/components/MapMask.jsx`)
Deck.gl viz app: SVG mask computed via `WebMercatorViewport.project()` in MapView.tsx

## Scenarios
Four scenarios: **Continuity**, **Overgrowth**, **Degrowth**, **Density**
Scenario images live in `public/Public/` and `Front end/Public/`

## Vercel deployment
- Repo: github.com/marcelbartumeu/ANDORRA-V1.9
- Auto-deploys on push to `main`
- Node version: set to 22.x in Vercel dashboard
- `react-leaflet` pinned to v4 (v5 requires React 19, project uses React 18)

## After editing the viz app
Always rebuild and commit the dist:
```bash
cd "Front end/dashboard/viz-abm-emotion-main"
npm run build
cd ../../..
git add -f "Front end/dashboard/viz-abm-emotion-main/dist/"
git commit -m "rebuild viz dist"
git push origin main
```

## Files not to touch
- `viz-abm-emotion-main/src/simulation_output/` — 2302 agent JSON files, do not modify
- `.gitattributes` — controls GitHub language stats
