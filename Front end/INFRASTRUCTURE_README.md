# Infrastructure Calculation Module

This module calculates infrastructure requirements (electricity, water, hospitals, schools, roads) for three population scenarios: Overgrowth (OG), Continuity (CO), and Degrowth (DG).

## Files

- `infrastructure.py` - Main calculation module
- `infrastructure_example.py` - Usage examples

## Quick Start

```python
from infrastructure import computeInfrastructureScenario, computeAllInfrastructureScenarios

# Calculate for a single scenario
og_result = computeInfrastructureScenario("OG")
print(og_result)

# Calculate for all scenarios
all_results = computeAllInfrastructureScenarios()
```

## Configuration

All constants are defined in `INFRASTRUCTURE_CONFIG` at the top of `infrastructure.py`. You can:

1. Modify the defaults directly in the file
2. Pass a custom config dict to the functions

### Key Constants

- **Populations**: OG=200k, CO=150k, DG=50k (baseline P0=87,097)
- **Electricity**: 3000 kWh/person/year baseline
- **Water**: 150 L/person/day, 12% household share
- **Hospitals**: 2.5 beds per 1000 people
- **Schools**: Based on 11,018 baseline students
- **Roads**: 269 km total baseline

## Output Structure

Each scenario returns:

```python
{
  "scenario": "OG",
  "population": 200000,
  "electricity": {
    "perCapita_kWh_year": 3000.0,
    "demand_kWh_year": 600000000.0,
    "capacity_kW": 136986.30,
    "renewableCapacity_kW": 82191.78,
    "fossilCapacity_kW": 54794.52
  },
  "water": {
    "perCapita_L_day": 150,
    "householdDemand_m3_year": 10950000.0,
    "totalDemand_m3_year": 91250000.0,
    "waterSecurityIndex": 0.110
  },
  "hospitals": {
    "baselineBeds": 217.74,
    "requiredBeds": 500.0,
    "deltaBeds": 282.26
  },
  "schools": {
    "students": 25300.53,
    "classrooms": 1012.02,
    "schools": 50.60
  },
  "roads": {
    "totalLength_km": 269,
    "perCapita_m": 1.345
  }
}
```

## Integration

To integrate with your existing model:

1. Import the module in `CALCULATOR.py`:
   ```python
   from infrastructure import computeAllInfrastructureScenarios
   ```

2. Add infrastructure calculations to your simulation:
   ```python
   infrastructure_results = computeAllInfrastructureScenarios()
   ```

3. Export to JSON for dashboard:
   ```python
   import json
   with open("infrastructure_results.json", "w") as f:
       json.dump(infrastructure_results, f, indent=2, default=str)
   ```

## Testing

Run the module directly to see test output:
```bash
python3 infrastructure.py
```

Run examples:
```bash
python3 infrastructure_example.py
```
