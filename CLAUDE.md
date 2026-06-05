# CLAUDE.md — Andorra V2.1

## Project overview
Interactive scenario modeling dashboard for Andorra, combining a React/Vite main app with an embedded ABM (agent-based model) visualization. Deployed on Vercel; also runs locally.

## Running locally
```bash
cd app
npm install
npm run dev          # → http://localhost:5173 (or 5174/5175 if busy)
```
No build step needed — the viz app dist is pre-committed.

## Repo structure
```
app/                       ← Main Vite/React app (root dir for Vercel)
  src/
    components/            ← Map views, KPI cards, overlays
    pages/                 ← Tab pages
    utils/                 ← Data helpers, chart utils
  public/
    model/                 ← GeoJSON data (bus, accessibility, population)
    Public/                ← Scenario images (overgrowth.png etc, Andorra1.jpg)
    js/                    ← scenarioData.js (loaded via script tag in index.html)
    growth_*.geojson       ← Growth scenario polygons
    tourism_*.geojson      ← Tourism layers
  viz-abm-emotion-main/    ← Standalone ABM viz (pre-built dist committed)
    src/pages/MapView.tsx          ← deck.gl agent map
    src/pages/AgentAnalyticsView.tsx
    src/services/SharedStateContext.tsx  ← loads 2302 agent JSON files
  transit-builder/         ← Transit route editing sub-app
  vercel.json              ← Build: copies viz dist → public/andorra/, then vite build
  vite.config.js           ← Dev middleware: serves /andorra/* from viz dist
data/
  raw/                     ← Raw geospatial files (gpkg, osm, graphml)
  scripts/                 ← Python generator scripts + source GeoJSON
hardware/                  ← Arduino hardware controller (Web Serial API)
unity/                     ← Unity/C# physical model server
research/                  ← Python research pipeline and agent profile generation
scenarios/                 ← Scenario parameter JSON files (continuity, degrowth, density, overgrowth)
paper/                     ← LaTeX papers
```

## Key architecture decisions
- **Viz app is an iframe** at `/andorra/` — loaded by MapVisualization.jsx for the "agents" layer
- **Vercel build**: `mkdir -p public/andorra && cp -r viz-abm-emotion-main/dist/. public/andorra/ && npm run build`
- **Vercel root dir**: must be set to `app` in Vercel dashboard
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
Scenario images live in `app/public/Public/`

## Vercel deployment
- Repo: github.com/marcelbartumeu/ANDORRA-V1.9
- Auto-deploys on push to `main`
- Node version: set to 22.x in Vercel dashboard
- **Root directory**: must be set to `app` in Vercel dashboard (was `Front end/dashboard`)
- `react-leaflet` pinned to v4 (v5 requires React 19, project uses React 18)

## After editing the viz app
Always rebuild and commit the dist:
```bash
cd app/viz-abm-emotion-main
npm run build
cd ../..
git add -f "app/viz-abm-emotion-main/dist/"
git commit -m "rebuild viz dist"
git push origin main
```

## Files not to touch
- `viz-abm-emotion-main/src/simulation_output/` — 2302 agent JSON files, do not modify
- `.gitattributes` — controls GitHub language stats

# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
