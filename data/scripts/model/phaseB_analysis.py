"""
Phase B reviewer-evidence harness (Andorra Clone Scenario Engine).

Generates, by re-running CALCULATOR.py components:
  B4 — inversion benchmark: GDP-driven endogenous-population back-cast (2011-2024)
       vs conventional population-as-trend baselines (CAGR, linear).
  B3 — multi-series validation: modelled vs observed endogenous series, RMSE%/MAPE.
  B2 — sensitivity matrix: +/-50% on key parameters -> 2049 endpoints.

Run:  python3 phaseB_analysis.py
Writes phaseB_results.json next to this file and prints readable tables.
"""
import json
from copy import deepcopy
from pathlib import Path

from CALCULATOR import (step_next, simulate_path,
                        extract_state_for_year, transform_data_from_list_format)

HERE = Path(__file__).resolve().parent
raw = json.load((HERE / "Current.json").open())
calib = json.load((HERE / "calibrated_params.json").open())

YEARS = list(range(2010, 2025))
obs = {y: extract_state_for_year(raw, y) for y in YEARS}

# 2010 initial-state defaults (mirror calibrate_historical_parameters)
DEFAULTS = {
    "Pop": 87097, "GDPpc": 42852.96, "Emp": 0.9852, "HPrice": 1332.734,
    "Tour": 9646656, "B": 10645, "ForeignBorn": 30000, "LE": 84.5,
    "WLB": 0.6, "Access": 0.922, "Income": 55533.6, "Salary": 2571,
    "Afford": 28.79843554, "NatCov": 0.9307, "CO2pc": 5.396,
    "CO2_total": 470000, "Ren": 0.931, "AQI": 8.40, "Water": 53655,
    "Temp": 7.46, "Rate": 0.03, "TourHomeDemand": 0.0,
    "BusinessFormation": 1450, "Marriages": 438, "Divorces": 98,
}
CALIB_PARAMS = {"gTFP": calib["gTFP"], "GDPpc_gamma2": calib["GDPpc_gamma2"],
                "Income_a1": calib["Income_a1"], "Income_a0": 0.0, "Income_a2": 0.0}


def rmse_pct(model, observed):
    pairs = [(model[y], observed[y]) for y in observed
             if y in model and observed[y] not in (None, 0)]
    if not pairs:
        return None
    return (sum(((m - o) / o) ** 2 for m, o in pairs) / len(pairs)) ** 0.5 * 100


def mape(model, observed):
    pairs = [(model[y], observed[y]) for y in observed
             if y in model and observed[y] not in (None, 0)]
    if not pairs:
        return None
    return sum(abs((m - o) / o) for m, o in pairs) / len(pairs) * 100


# ----------------------------------------------------------------------
# B4 / B3 — GDP-driven endogenous-population back-cast (2011-2024)
# Force observed GDPpc (force_gdp), let population evolve endogenously.
# ----------------------------------------------------------------------
s2010 = deepcopy(obs[2010])
for k, v in DEFAULTS.items():
    s2010.setdefault(k, v)
s2010["Year"] = 2010

cur = deepcopy(s2010)
model = {2010: deepcopy(cur)}
for y in range(2011, 2025):
    o = obs[y]
    bundle = {
        "state": deepcopy(cur),
        "params": deepcopy(CALIB_PARAMS),
        "exog": {
            "GDPpc_target": o.get("GDPpc", cur.get("GDPpc")),
            "force_gdp": True, "force_pop": False,
            "Tour_target": o.get("Tour", cur.get("Tour")), "force_tour": True,
            "B_target": o.get("B", cur.get("B")), "force_build": True,
            "scenario_name": "Continuity", "target_year": y,
        },
    }
    ns = step_next(bundle)["state"]
    ns["Year"] = y
    model[y] = ns
    cur = ns

# Observed population series
Pobs = {y: obs[y]["Pop"] for y in YEARS if obs[y].get("Pop") is not None}
ys = sorted(Pobs)
y0, yT = ys[0], ys[-1]

# Conventional baselines (population as exogenous trend)
g = (Pobs[yT] / Pobs[y0]) ** (1.0 / (yT - y0)) - 1.0
cagr = {y: Pobs[y0] * (1 + g) ** (y - y0) for y in ys}
xs = [y - y0 for y in ys]
yvals = [Pobs[y] for y in ys]
n = len(xs)
sx, sy = sum(xs), sum(yvals)
sxx = sum(x * x for x in xs)
sxy = sum(x * v for x, v in zip(xs, yvals))
slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
intercept = (sy - slope * sx) / n
linear = {y: intercept + slope * (y - y0) for y in ys}
inverted = {y: model[y]["Pop"] for y in ys if y in model}

# Evaluate on 2011-2024 (exclude 2010 shared anchor)
eval_years = {y: Pobs[y] for y in ys if y >= 2011}
benchmark = {
    "inverted_gdp_driven": {"rmse_pct": rmse_pct(inverted, eval_years), "mape": mape(inverted, eval_years)},
    "baseline_cagr":       {"rmse_pct": rmse_pct(cagr, eval_years),     "mape": mape(cagr, eval_years)},
    "baseline_linear":     {"rmse_pct": rmse_pct(linear, eval_years),   "mape": mape(linear, eval_years)},
}
# Two-regime reproduction
regime = {
    "observed":  {"d2010_2013": Pobs[2013] - Pobs[2010], "d2015_2024": Pobs[2024] - Pobs[2015]},
    "inverted":  {"d2010_2013": inverted[2013] - inverted[2010], "d2015_2024": inverted[2024] - inverted[2015]},
}

# ----------------------------------------------------------------------
# B3 — multi-series validation (endogenous outputs only)
# ----------------------------------------------------------------------
ENDOG = {"Pop": "Population", "Salary": "Avg monthly salary",
         "Afford": "Housing affordability (% income)", "CO2pc": "CO2 per capita",
         "NatCov": "Natural coverage", "LE": "Life expectancy", "WLB": "Work-life balance"}
validation = {}
for var, label in ENDOG.items():
    o_series = {y: obs[y].get(var) for y in range(2011, 2025) if obs[y].get(var) is not None}
    m_series = {y: model[y].get(var) for y in o_series}
    validation[var] = {"label": label, "rmse_pct": rmse_pct(m_series, o_series),
                       "mape": mape(m_series, o_series), "n": len(o_series)}

# ----------------------------------------------------------------------
# B2 — sensitivity matrix (+/-50% -> 2049 endpoints, Continuity)
# ----------------------------------------------------------------------
current = transform_data_from_list_format(raw)
current.setdefault("params", {})
for k in ("gTFP", "GDPpc_gamma2", "Income_a1"):
    current["params"][k] = calib[k]
    current["params"]["_calib_" + k] = calib[k]


def endpoint(ts):
    last = ts[-1]
    return {"Pop": last.get("Pop"), "Tour": last.get("Tour"),
            "Afford": last.get("Afford"), "CO2_total": last.get("CO2_total")}


base_ts, _ = simulate_path(current, "Continuity", years=25, start_year=2024)
base = endpoint(base_ts)

PARAMS = {"beta_gdp_lag1": 0.40, "beta_gdp_lag2": 0.10, "beta_afford": 0.10,
          "afford_threshold": 0.30, "tour_exp_B": 0.4, "tour_exp_P": 0.2,
          "tour_friction": 3.0}
sensitivity = {"base_2049": base, "params": {}}
for name, val in PARAMS.items():
    row = {}
    for factor, lab in ((0.5, "low"), (1.5, "high")):
        ts, _ = simulate_path(current, "Continuity", years=25, start_year=2024,
                              param_overrides={name: val * factor})
        ep = endpoint(ts)
        row[lab] = {k: ((ep[k] - base[k]) / base[k] * 100 if base[k] else None) for k in ep}
    sensitivity["params"][name] = row

# ----------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------
results = {"benchmark_B4": benchmark, "regime_B4": regime,
           "validation_B3": validation, "sensitivity_B2": sensitivity,
           "obs_pop": Pobs, "inverted_pop": inverted}
(HERE / "phaseB_results.json").write_text(json.dumps(results, indent=2, default=float))

print("=" * 68)
print("B4 — INVERSION BENCHMARK (population back-cast 2011-2024)")
print("=" * 68)
print(f"  observed 2010 Pop = {Pobs[y0]:.0f}   2024 Pop = {Pobs[yT]:.0f}")
print(f"  {'model':<26}{'RMSE %':>10}{'MAPE %':>10}")
for k, v in benchmark.items():
    print(f"  {k:<26}{v['rmse_pct']:>10.2f}{v['mape']:>10.2f}")
print(f"  two-regime  observed: 2010-13 {regime['observed']['d2010_2013']:+.0f}, "
      f"2015-24 {regime['observed']['d2015_2024']:+.0f}")
print(f"  two-regime  inverted: 2010-13 {regime['inverted']['d2010_2013']:+.0f}, "
      f"2015-24 {regime['inverted']['d2015_2024']:+.0f}")

print("\n" + "=" * 68)
print("B3 — MULTI-SERIES VALIDATION (modelled vs observed, endogenous)")
print("=" * 68)
print(f"  {'variable':<34}{'RMSE %':>9}{'MAPE %':>9}{'n':>4}")
for var, v in validation.items():
    r = f"{v['rmse_pct']:.2f}" if v['rmse_pct'] is not None else "n/a"
    m = f"{v['mape']:.2f}" if v['mape'] is not None else "n/a"
    print(f"  {v['label']:<34}{r:>9}{m:>9}{v['n']:>4}")

print("\n" + "=" * 68)
print("B2 — SENSITIVITY (+/-50%, % change in 2049 Continuity endpoint)")
print("=" * 68)
print(f"  base 2049: Pop={base['Pop']:.0f}  Tour={base['Tour']:.2e}  "
      f"Afford={base['Afford']:.1f}  CO2={base['CO2_total']:.2e}")
print(f"  {'param (dir)':<24}{'Pop%':>9}{'Tour%':>9}{'Afford%':>9}{'CO2%':>9}")
for name, row in sensitivity["params"].items():
    for lab in ("low", "high"):
        d = row[lab]
        def f(x):
            return f"{x:+.1f}" if x is not None else "  n/a"
        print(f"  {name+' ('+lab+')':<24}{f(d['Pop']):>9}{f(d['Tour']):>9}"
              f"{f(d['Afford']):>9}{f(d['CO2_total']):>9}")
print("\nWrote phaseB_results.json")
