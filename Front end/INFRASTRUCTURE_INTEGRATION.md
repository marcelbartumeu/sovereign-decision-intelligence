# Infrastructure Integration Summary

## Overview
Infrastructure calculations have been fully integrated into the existing codebase. Infrastructure data now flows through the entire system and appears in:
- JSON timeseries files (when calculator runs)
- scenarioData.js (for dashboard)
- State objects in CALCULATOR.py

## Changes Made

### 1. CALCULATOR.py
- **Imported** `infrastructure` module
- **Added infrastructure calculations** to `step_next()` function
- Infrastructure is calculated based on:
  - Current population (`Pop_next`)
  - Scenario name (passed through `exog["scenario_name"]`)
- **Added infrastructure fields** to state output:
  - Electricity: PerCapita_kWh_year, Demand_kWh_year, Capacity_kW, Renewable_kW, Fossil_kW
  - Water: PerCapita_L_day, Household_m3_year, Total_m3_year, SecurityIndex
  - Hospitals: BaselineBeds, RequiredBeds, DeltaBeds
  - Schools: Students, Classrooms, Schools
  - Roads: TotalLength_km, PerCapita_m

### 2. scenarioData.js
- **Added infrastructure data** to all scenarios:
  - `current` (2024 baseline)
  - `continuity` (2034)
  - `overgrowth` (2034)
  - `degrowth` (2034)

### 3. Infrastructure Module (infrastructure.py)
- Standalone module with all infrastructure formulas
- Configurable constants
- Pure functions for easy testing

## How It Works

1. **Baseline (2024)**: Infrastructure is calculated when `transform_data_from_list_format()` processes Current.json
2. **Future Scenarios**: Infrastructure is calculated each year in `step_next()` based on:
   - Current population
   - Scenario type (determines renewable share, etc.)
3. **JSON Output**: When you run `python3 CALCULATOR.py`, all timeseries JSON files will include infrastructure fields
4. **Dashboard**: scenarioData.js contains infrastructure data for all scenarios

## Infrastructure Fields in State

Each state object now includes:

```javascript
{
  // Electricity
  ElectricityPerCapita_kWh_year: 3000,
  ElectricityDemand_kWh_year: 261291000,
  ElectricityCapacity_kW: 59655.48,
  ElectricityRenewable_kW: 29827.74,
  ElectricityFossil_kW: 29827.74,
  
  // Water
  WaterPerCapita_L_day: 150,
  WaterHousehold_m3_year: 4767805.5,
  WaterTotal_m3_year: 39731712.5,
  WaterSecurityIndex: 0.2516,
  
  // Hospitals
  HospitalBaselineBeds: 217.74,
  HospitalRequiredBeds: 217.74,
  HospitalDeltaBeds: 0,
  
  // Schools
  SchoolStudents: 11018,
  SchoolClassrooms: 440.72,
  SchoolSchools: 22.04,
  
  // Roads
  RoadTotalLength_km: 269,
  RoadPerCapita_m: 3.09
}
```

## Next Steps

1. **Run the calculator** to generate updated JSON files with infrastructure:
   ```bash
   python3 CALCULATOR.py
   ```

2. **Update historical series** in scenarioData.js (optional):
   - Extract infrastructure series from timeseries JSON files
   - Add to `historicalSeries` object in scenarioData.js

3. **Use in dashboard**:
   - Infrastructure fields are now available in `scenarioData`
   - Can be accessed like: `scenarioData.current.ElectricityCapacity_kW`
   - Can be displayed in KPI cards or charts

## Notes

- Infrastructure calculations use **actual population** from each time step, not fixed scenario targets
- Scenario type affects:
  - Renewable energy share (OG: 60%, CO/DG: 50%)
  - All other calculations scale with population
- The `Y_safe` water constant is configurable in `INFRASTRUCTURE_CONFIG` (currently 10M m³/year)
