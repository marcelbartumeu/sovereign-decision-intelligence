"""
Export rich agent profiles + precomputed dashboard aggregates for the viz Agent
Analytics tab. The trip chunks only carry {id,nat,inc,emotion,path,ts,bounds};
this adds the psychometric / political / economic / mobility profile, the agent's
daily-tour metadata, per-layer social-network degree, and population-level
aggregates (with SAIG ground-truth targets) so the analytics tab can show real
data instead of emotion placeholders.

Outputs (app/public/model/):
  agent_profiles_{0..5}.json   per-agent compact profile (loaded lazily by the tab)
  agent_aggregates.json        precomputed population distributions for dashboards

Usage:
    cd research/profile_generation
    python export_profiles.py
"""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

SRC       = Path(__file__).parent / "results" / "andorra_population"
APP_MODEL = Path(__file__).parents[2] / "app" / "public" / "model"
CHUNKS    = 6

# SAIG 2023 ground-truth marginals (mirrors config.ANDORRA targets).
SAIG = {
    "nationality": {"Andorran": 0.356, "Spanish": 0.335, "Portuguese": 0.171,
                    "French": 0.066, "Other": 0.072},
    "age": {"0–14": 0.152, "15–24": 0.137, "25–39": 0.254,
            "40–54": 0.243, "55–64": 0.108, "65+": 0.106},
    "income": {"precarious": 0.12, "low": 0.15, "lower_middle": 0.27, "middle": 0.22,
               "upper_middle": 0.13, "comfortable": 0.08, "wealthy": 0.03},
}
AGE_BANDS = ["0–14", "15–24", "25–39", "40–54", "55–64", "65+"]
PP_KEYS = [f"D{i}" for i in range(3, 29)]   # place-preference layers D3..D28


def age_band(age: int) -> str:
    if age < 15: return AGE_BANDS[0]
    if age < 25: return AGE_BANDS[1]
    if age < 40: return AGE_BANDS[2]
    if age < 55: return AGE_BANDS[3]
    if age < 65: return AGE_BANDS[4]
    return AGE_BANDS[5]


def hist(values, lo=0.0, hi=1.0, bins=20):
    if not len(values):
        return [0] * bins
    h, _ = np.histogram(np.clip(values, lo, hi), bins=bins, range=(lo, hi))
    return [int(x) for x in h]


def shares(counter: Counter, n: int) -> dict:
    return {k: round(v / n, 4) for k, v in counter.items()} if n else {}


def r3(x):
    try: return round(float(x), 3)
    except (TypeError, ValueError): return None


def main():
    print("Loading population / households / schedules / network...")
    population = json.load(open(SRC / "population.json"))
    schedules  = json.load(open(SRC / "schedules.json"))
    sched_by_id = {s["agent_id"]: s for s in schedules}

    # ── Per-agent network degree per layer ────────────────────────────────────
    deg = {L: Counter() for L in ("household", "workplace", "school", "community")}
    for L in deg:
        path = SRC / f"network_{L}.csv"
        if not path.exists():
            continue
        with open(path) as f:
            r = csv.reader(f); next(r, None)
            for src, dst in r:
                deg[L][src] += 1
                deg[L][dst] += 1

    # ── Build compact per-agent profiles ──────────────────────────────────────
    print("Building profiles...")
    profiles = []
    for a in population:
        aid = a["agent_id"]
        minor = bool(a.get("is_minor"))
        rec = {
            "id": aid,
            "age": a.get("age"), "gender": a.get("gender"),
            "nat": a.get("nationality"), "parish": a.get("parish"),
            "edu": a.get("education_level"), "emp": a.get("employment_status"),
            "sector": a.get("work_sector"), "inc": a.get("income_bracket"),
            "yia": a.get("years_in_andorra"), "hh": a.get("household_composition"),
            "role": a.get("household_role"), "xborder": bool(a.get("is_cross_border")),
            "minor": minor,
            "net": [deg["household"].get(aid, 0), deg["workplace"].get(aid, 0),
                    deg["school"].get(aid, 0), deg["community"].get(aid, 0)],
        }
        # place preferences (present for adults and children)
        pp = a.get("place_preferences") or {}
        rec["pp"] = [r3(pp.get(k)) for k in PP_KEYS]

        # daily-tour metadata (from coherent schedules)
        s = sched_by_id.get(aid)
        if s and s.get("trips"):
            rec["trips"] = [{"t": t["activity_type"], "m": t["mode"],
                             "d": round(t["departure_min"], 1), "du": round(t["duration_min"], 1)}
                            for t in s["trips"]]

        # psychometric / political / economic — adults only
        if not minor:
            p = a.get("personality", {})
            rec["big5"] = [r3(p.get(k)) for k in
                           ("openness", "conscientiousness", "extraversion",
                            "agreeableness", "neuroticism")]
            sv = a.get("schwartz_values", {})
            rec["sv"] = [sv.get("primary"), sv.get("secondary"), sv.get("tertiary")]
            be = a.get("behavioral_economics", {})
            rec["becon"] = [r3(be.get("loss_aversion")), r3(be.get("discount_rate")),
                            r3(be.get("present_bias"))]
            ec = a.get("economic", {})
            rec["econ"] = [r3(ec.get("financial_stress")), r3(ec.get("savings_orientation")),
                           r3(ec.get("price_sensitivity")),
                           r3(ec.get("employment_security_perception"))]
            so = a.get("social", {})
            rec["soc"] = [r3(so.get("bonding_capital")), r3(so.get("bridging_capital")),
                          r3(so.get("civic_participation"))]
            mo = a.get("mobility", {})
            rec["mob"] = {"mode": mo.get("primary_mode"), "tw": r3(mo.get("transit_willingness")),
                          "wr": r3(mo.get("walking_radius_km")),
                          "xbf": mo.get("cross_border_frequency"),
                          "cd": bool(mo.get("car_dependent"))}
            po = a.get("political", {})
            rec["pol"] = {"ea": r3(po.get("economic_axis")), "sa": r3(po.get("social_axis")),
                          "le": r3(po.get("local_engagement")),
                          "trust": {k: r3(v) for k, v in (po.get("institutional_trust") or {}).items()},
                          "sal": {k: r3(v) for k, v in (po.get("issue_salience") or {}).items()}}
            g = a.get("goals", {})
            rec["goals"] = {"st": g.get("short_term", []), "lt": g.get("long_term", []),
                            "fear": g.get("primary_fear", "")}
            rec["sum"] = a.get("summary", "")
        profiles.append(rec)

    # ── Write profile chunks ──────────────────────────────────────────────────
    APP_MODEL.mkdir(parents=True, exist_ok=True)
    per = (len(profiles) + CHUNKS - 1) // CHUNKS
    for c in range(CHUNKS):
        chunk = profiles[c * per:(c + 1) * per]
        with open(APP_MODEL / f"agent_profiles_{c}.json", "w") as f:
            json.dump(chunk, f, separators=(",", ":"))
    total_mb = sum((APP_MODEL / f"agent_profiles_{c}.json").stat().st_size for c in range(CHUNKS)) / 1e6
    print(f"  wrote {CHUNKS} profile chunks ({total_mb:.1f} MB, {len(profiles):,} agents)")

    # ── Precompute dashboard aggregates ───────────────────────────────────────
    print("Computing aggregates...")
    adults = [a for a in population if not a.get("is_minor")]
    n_all, n_ad = len(population), len(adults)

    def cnt(field, src=population):
        return Counter(a.get(field) for a in src if a.get(field) is not None)

    # demographics (realized vs SAIG)
    nat_real = shares(cnt("nationality"), n_all)
    age_real = shares(Counter(age_band(a["age"]) for a in population if a.get("age") is not None), n_all)
    inc_real = shares(cnt("income_bracket"), n_all)
    demographics = {
        "nationality": {"realized": nat_real, "target": SAIG["nationality"]},
        "age": {"realized": {b: age_real.get(b, 0) for b in AGE_BANDS}, "target": SAIG["age"],
                "order": AGE_BANDS},
        "income": {"realized": inc_real, "target": SAIG["income"],
                   "order": list(SAIG["income"].keys())},
        "education": shares(cnt("education_level", adults), n_ad),
        "employment": shares(cnt("employment_status", adults), n_ad),
        "parish": shares(cnt("parish"), n_all),
        "gender": shares(cnt("gender"), n_all),
        "n_agents": n_all, "n_adults": n_ad, "n_children": n_all - n_ad,
    }

    # mobility & schedule (from coherent schedules)
    mode_ct = Counter(); dep = []; dur = []; act_ct = Counter()
    for s in schedules:
        for t in s.get("trips", []):
            mode_ct[t["mode"]] += 1
            dep.append(t["departure_min"]); dur.append(t["duration_min"])
            act_ct[t["activity_type"]] += 1
    dep = np.array(dep); dur = np.array(dur)
    dep_hist, _ = np.histogram(dep, bins=48, range=(0, 1440))   # half-hour bins
    dur_hist, _ = np.histogram(np.clip(dur, 0, 60), bins=30, range=(0, 60))
    mobility = {
        "mode_share": dict(mode_ct),
        "departure_hist_30min": [int(x) for x in dep_hist],
        "duration_hist_min": [int(x) for x in dur_hist], "duration_bin_max": 60,
        "activity_mix": dict(act_ct),
        "total_trips": int(mode_ct.total()),
        "cross_border_share": round(sum(1 for a in population if a.get("is_cross_border")) / n_all, 4),
        "primary_mode": shares(Counter(
            (a.get("mobility") or {}).get("primary_mode") for a in adults
            if (a.get("mobility") or {}).get("primary_mode")), n_ad),
    }

    # political & civic (adults)
    def pol(a, *keys, d=None):
        v = a.get("political", {})
        for k in keys: v = (v or {}).get(k, d) if isinstance(v, dict) else d
        return v
    ea = np.array([pol(a, "economic_axis") for a in adults if pol(a, "economic_axis") is not None])
    sa = np.array([pol(a, "social_axis") for a in adults if pol(a, "social_axis") is not None])
    compass, _, _ = np.histogram2d(ea, sa, bins=12, range=[[0, 1], [0, 1]])
    sal_topics = ["housing", "environment", "immigration", "economy", "tourism"]
    trust_dom = ["government", "legal_system", "employers", "media", "interpersonal"]
    def mean_of(getter):
        vals = [getter(a) for a in adults]
        vals = [v for v in vals if v is not None]
        return round(float(np.mean(vals)), 3) if vals else None
    political = {
        "compass_12x12": [[int(x) for x in row] for row in compass],
        "issue_salience_mean": {k: mean_of(lambda a, k=k: (pol(a, "issue_salience") or {}).get(k)) for k in sal_topics},
        "institutional_trust_mean": {k: mean_of(lambda a, k=k: (pol(a, "institutional_trust") or {}).get(k)) for k in trust_dom},
        "local_engagement_hist": hist([pol(a, "local_engagement") for a in adults if pol(a, "local_engagement") is not None]),
        "schwartz_primary": shares(Counter((a.get("schwartz_values") or {}).get("primary")
                                            for a in adults if (a.get("schwartz_values") or {}).get("primary")), n_ad),
    }

    # economic stress (adults), overall + by income bracket
    def econ_vals(field):
        return np.array([(a.get("economic") or {}).get(field) for a in adults
                         if (a.get("economic") or {}).get(field) is not None])
    inc_order = list(SAIG["income"].keys())
    fs_by_inc = {}
    for b in inc_order:
        vals = [(a.get("economic") or {}).get("financial_stress") for a in adults
                if a.get("income_bracket") == b and (a.get("economic") or {}).get("financial_stress") is not None]
        fs_by_inc[b] = round(float(np.mean(vals)), 3) if vals else None
    economic = {
        "financial_stress_hist": hist(econ_vals("financial_stress")),
        "price_sensitivity_hist": hist(econ_vals("price_sensitivity")),
        "employment_security_hist": hist(econ_vals("employment_security_perception")),
        "savings_orientation_hist": hist(econ_vals("savings_orientation")),
        "financial_stress_by_income": {"order": inc_order, "mean": fs_by_inc},
        "hist_bins": 20,
    }

    # personality (adults) — distributions + means
    big5_keys = ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism")
    def big5_vals(k):
        return np.array([(a.get("personality") or {}).get(k) for a in adults
                         if (a.get("personality") or {}).get(k) is not None])
    personality = {k: {"hist": hist(big5_vals(k)), "mean": round(float(big5_vals(k).mean()), 3)}
                   for k in big5_keys}

    # network (from run_meta)
    net = {}
    rm = SRC / "run_meta.json"
    if rm.exists():
        net = json.load(open(rm)).get("network_metrics", {})

    agg = {
        "n_agents": n_all, "n_adults": n_ad, "n_children": n_all - n_ad,
        "demographics": demographics, "mobility": mobility, "political": political,
        "economic": economic, "personality": personality, "network": net,
    }
    with open(APP_MODEL / "agent_aggregates.json", "w") as f:
        json.dump(agg, f, separators=(",", ":"))
    sz = (APP_MODEL / "agent_aggregates.json").stat().st_size / 1e3
    print(f"  wrote agent_aggregates.json ({sz:.0f} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
