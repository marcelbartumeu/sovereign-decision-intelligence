# Candace — Onboarding: Narrative Scrollytelling Landing Page

Welcome, Candace! This branch (`scrollytelling-landing`) is yours to build the narrative
scrollytelling landing page for the Andorra project, per the plan
(*Andorra Narrative Data Visualization Plan*). This doc points you to the exact
data and components you'll plug into so you don't have to reverse-engineer the repo.

## Run it locally
```bash
cd app
npm install
npm run dev            # → http://localhost:5173
```
No build step needed for the main app in dev. (Vercel handles production builds.)

## Branch & workflow
- You're on **`scrollytelling-landing`**, branched from `intelligence-theme` (the current
  working state, incl. the "SPECTRE" intelligence-console theme).
- Commit and push to **this branch only**. Open a PR when you want feedback.
- **Do not commit large data or build output** — `research/.../results/`, `app/dist/`,
  `app/transit-builder/dist/`, and `app/public/model/andorra_trips.json` are gitignored on
  purpose (they're huge / regenerable). The front-end data you need is small and already tracked.

## The data you'll use (all under `app/public/`)

Everything is plain JSON/GeoJSON loaded client-side — no backend.

### Scenario KPIs over time — the spine of the story
`app/public/model/<Scenario>_timeseries.json` for the four scenarios:
**Continuity, Density, Overgrowth, Degrowth**
- 25 yearly rows, **2025 → 2049**, each with ~45 KPIs.
- Key fields: `Year`, `Pop`, `ForeignBorn`, `Access`, `LE` (life expectancy), `GDPpc`,
  `Income`, `CO2_total`, `CO2pc`, `Ren` (renewables share), `AQI`, `Water`, `Tour` (tourism),
  `GDP`, `SchoolStudents`, `HospitalRequiredBeds`, `ElectricityDemand_kWh_year`,
  `RoadTotalLength_km`, `RoadPerCapita_m`.
- Note: the plan's "baseline" ≈ **Continuity**.

Supporting:
- `app/public/model/<Scenario>_final.json` — 2050 endpoint snapshot (single object).
- `app/public/model/Scenario_Rollup.json` — `start` vs `end` per scenario (great for
  2025-vs-2050 comparisons / the closer).
- `app/public/model/Current.json` — historical 2010–2024 actuals (population, etc.).
- `scenarios/<id>.json` — the assumption parameters behind each scenario (growth rates, etc.).

### Map layers (GeoJSON)
| Layer | File(s) |
|---|---|
| Country outline | `app/public/andorra_boundary.geojson` |
| Buildable-land constraint | `app/public/growth_constraints.geojson`, `app/public/model/andorra_protected_areas.geojson` |
| Growth by scenario | `app/public/growth_{continuity,density,overgrowth,degrowth}.geojson` |
| Population density (H3 hexes) | `app/public/accessibility_population.geojson` |
| Accessibility / infrastructure | `app/public/accessibility_{streets,schools}.geojson`, `app/public/model/bus_{routes,stops}.geojson` |
| Tourism | `app/public/tourism_*.geojson` |

## Plan sections → what to wire up
1. **Andorra Today** — base map (`BaseMapView.jsx`, Esri satellite) + `Current.json` to frame
   today's ~88k population and the core question.
2. **Buildable Land Constraint** — `growth_constraints.geojson` + `andorra_protected_areas.geojson`
   + H3 hexes from `accessibility_population.geojson`. Build the "468 km² → ~70 → ~40" sequence.
3. **Sprawl vs Density** — `growth_overgrowth.geojson` vs `growth_density.geojson` side by side.
4. **Population Scenarios to 2050** — `*_timeseries.json` with a year slider (2025–2049) and a
   scenario toggle; drive KPI cards off the active row.
5. **Accessibility & Infrastructure** — accessibility GeoJSON + KPIs (`Access`, `RoadPerCapita_m`,
   `ElectricityDemand_kWh_year`, `HospitalRequiredBeds`, `SchoolStudents`).
6. **Choose Andorra's Future** — compare scenarios using `Scenario_Rollup.json` / `*_final.json`;
   end with the reflective prompt.

## Reusable building blocks (already in `app/src/`)
- `components/KpiCard.jsx` — KPI tile.
- `components/BaseMapView.jsx` — Leaflet base map (Esri satellite).
- `components/MapMask.jsx` — the black projection-corner mask (see corners below).
- `utils/chartUtils.js` — chart helpers.

For your scroll engine, the plan suggests `IntersectionObserver` to detect the active
step and a small **`story_steps.json`** config (you'll author this) mapping each scroll
section → `{ scenario, year, layer, kpis, annotation }`. Good home for it:
`app/public/story_steps.json` or `app/src/data/story_steps.json`.

## If you render maps, use these projection corners (all maps must match)
```
NW: [42.694543, 1.393847]
NE: [42.697242, 1.801074]
SE: [42.396861, 1.803713]
SW: [42.394176, 1.39849]
```

## Don't touch
- `app/viz-abm-emotion-main/src/simulation_output/` — large agent dataset.
- `.gitattributes` — controls GitHub language stats.
- The gitignored large-data paths listed above (don't re-add them to git).

Questions about the data or where something lives → ask Marcel.
