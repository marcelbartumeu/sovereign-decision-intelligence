# Andorra scenario model (CALCULATOR)

This folder contains the Python model that produces scenario projections (2025–2035) from the 2024 baseline.

## 1. How to regenerate the data

### Prerequisites

- Python 3
- Input file: `Current.json` (or `current.json`) in this folder, with 2024 baseline data in the expected format (see `transform_data_from_list_format` in `CALCULATOR.py`).

### Run the calculator

From the **Front end/model** directory:

```bash
cd "Front end/model"
python3 CALCULATOR.py
```

This will:

- Read `Current.json` (or `current.json`) as the 2024 baseline.
- Run the model for **Overgrowth**, **Degrowth**, **Continuity**, and **Density** (11 years each, 2025–2035).
- Write outputs in the same folder:
  - `Overgrowth_timeseries.json`, `Overgrowth_final.json`
  - `Degrowth_timeseries.json`, `Degrowth_final.json`
  - `Continuity_timeseries.json`, `Continuity_final.json`
  - `Density_timeseries.json`, `Density_final.json`
  - `Scenario_Rollup.json` (summary).

### Using the new data in the dashboard

The **HTML dashboard** (`Dashboard.HTML`) and the **React dashboard** load scenario data from **`Front end/js/scenarioData.js`**. After regenerating the JSON with `CALCULATOR.py`, update that file by running:

```bash
python3 update_scenario_data_js.py
```

(from the **Front end/model** directory). This script reads the `*_final.json` and `*_timeseries.json` files and updates the `continuity`, `overgrowth`, `degrowth`, and `density` sections (and their `timeseriesData`) in `Front end/js/scenarioData.js`, leaving the `current` scenario and `historicalSeries` unchanged.

If you use the React dashboard, copy the updated file into its public folder so the app loads the new data:

```bash
cp ../js/scenarioData.js ../dashboard/public/js/scenarioData.js
```

Then reload the dashboard (and restart the dev server if needed).

---

## 2. Model design: 2024 → 2025 transition

Projections are **scientifically calculated** from the model equations; values are not forced into bands.

- **Population, tourism, buildings**  
  Driven by scenario targets. The path is a **linear interpolation** from 2024 to the 2035 target, so 2025 is already close to 2024 by construction.

- **Foreign-born population**  
  - From **2025 onward** the usual migration rule applies: net migration is attributed to foreign-born (with `alpha_fb`), including when net migration is negative.  
  - For the **first step only (2024 → 2025)** the model uses **continuity of demographic composition**: the foreign-born **share** is kept equal to 2024, and the level is set as  
    `FB_next = (FB_2024 / Pop_2024) * Pop_next`.  
  So the 2025 value is determined by the 2024 share and the (already interpolated) 2025 population, with no arbitrary clamping. From 2026 onward the full migration model applies.

- **All other variables**  
  Computed from the model equations (economic, health, environment, infrastructure, etc.) using the updated population, tourism, and buildings. There is no post-hoc smoothing or forcing; if you want a gentler path in the first years, adjust the scenario targets or the interpolation (e.g. non-linear ramp) in the model code.
