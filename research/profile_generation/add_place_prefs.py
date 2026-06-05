"""
Backfill place_preferences into existing archetypes.json and population.json,
then run the four mathematical validity metrics against the population.

Run from research/profile_generation/:
    python add_place_prefs.py

Outputs
───────
  archetypes.json  — place_preferences added / updated on each archetype
  population.json  — place_preferences added / updated on each population agent
  Printed validity report (ARA, MDP, SCC, SEF)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from place_preferences import compute_place_preferences, PlacePreferenceValidator

POP_DIR = Path(__file__).parent / "results" / "andorra_population"

for fname in ("archetypes.json", "population.json"):
    path = POP_DIR / fname
    if not path.exists():
        print(f"  {fname} not found, skipping")
        continue
    print(f"Processing {fname}...", end=" ", flush=True)
    with open(path) as f:
        data = json.load(f)
    for agent in data:
        agent["place_preferences"] = compute_place_preferences(agent)
    with open(path, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"{len(data):,} agents  {path.stat().st_size / 1e6:.1f} MB")

# ── Mathematical validity metrics ──────────────────────────────────────────────
print("\nRunning mathematical validity metrics on population.json ...")
with open(POP_DIR / "population.json") as f:
    population = json.load(f)

# 10 k agents is sufficient for stable metric estimates
sample    = population[:10_000]
validator = PlacePreferenceValidator(sample)
report    = validator.report()

print(f"\n{'─'*54}")
print(f"  Place Preference Validity Report  (n={report['n_profiles']:,})")
print(f"{'─'*54}")
print(f"  ARA  Activity Rate Alignment     {report['ara']:.4f}")
print(f"  MDP  Monotone Demographic Preds  {report['mdp']:.4f}")
print(f"  SCC  Social Cluster Coherence    {report['scc']:.4f}")
print(f"  SEF  Shannon Entropy Floor       {report['sef']:.4f}")
print(f"{'─'*54}")
print(f"  Composite                        {report['composite']:.4f}")
print(f"{'─'*54}")

print("\nARA detail (synthetic mean vs MTUS reference):")
for did, d in sorted(report["detail_ara"].items()):
    flag = "!" if d["relative_error"] > 0.25 else " "
    print(f"  {flag} {did:<4}  syn={d['synthetic_mean']:.3f}  "
          f"ref={d['reference']:.3f}  err={d['relative_error']:.3f}")

print("\nMDP detail (Spearman signed correlations with demographics):")
fails  = [r for r in report["detail_mdp"] if not r["pass"]]
passes = [r for r in report["detail_mdp"] if r["pass"]]
print(f"  Passed: {len(passes)}/{len(report['detail_mdp'])}")
if fails:
    print("  Failed checks:")
    for r in fails:
        print(f"    {r['layer']} × {r['feature']:3s}  expected={r['expected']:8s}  ρ={r['rho']}")

print("\nSCC detail (social cluster pairwise Pearson r):")
for r in report["detail_scc"]:
    mark = "pass" if r["pass"] else "FAIL"
    print(f"  {r['pair']}  r={r['r']:.3f}  [{mark}]")

sef_d = report["detail_sef"]
print(f"\nSEF: mean H_norm={sef_d['mean_h_norm']:.3f}  "
      f"min={sef_d['min_h_norm']:.3f}  "
      f"fraction≥{sef_d['threshold']}={sef_d['fraction_above']:.3f}")

print("\nDone.")
