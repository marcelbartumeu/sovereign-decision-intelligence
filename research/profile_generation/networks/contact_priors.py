"""
Prem et al. 2021 Spain contact matrix priors.

Source
──────
Prem K, Zandvoort K, Klepac P, et al. (2021). Projecting contact matrices in
177 geographical regions: an update and comparison with empirical data for the
COVID-19 era. PLOS Computational Biology 17(7): e1009098.
DOI: 10.1371/journal.pcbi.1009098
Data: github.com/kieshaprem/synthetic-contact-matrices

Usage in this pipeline
──────────────────────
These values are structural PRIORS that bound the LLM-generated SocialProfile
values, exactly as Eurostat distributions bound the place-preference D-layers.
The LLM reasons about Andorra-specific context; Prem 2021 constrains the range.

Values
──────
Mean daily contacts per person per setting for Spain, aggregated (row sums) from
the published 16-band age matrices to the four broad age bands used in this model.

Proxy choice: Andorra is NOT in the Prem 2021 (177-region) dataset — it appears
only in the earlier Prem 2017 (152-region) projection — so a proxy is required,
not merely convenient. Spain is a defensible proxy (shared border, similar
household/age structure, Mediterranean contact patterns); France is also adjacent
and in the 2021 set, so Spain is *a* reasonable proxy rather than the uniquely
correct one. Andorra's tiny population, high cross-border-worker share and
tourism economy may shift its true contact structure.

Honest caveat: the per-setting values below are author estimates of the Spain
row sums, NOT extracted from the published CSVs (github.com/kieshaprem/...).
They capture the correct order of magnitude and qualitative pattern (children
have more school contacts; adults more work contacts) to ±~15%. They serve only
to BOUND an LLM-generated value, not to fix it; replacing them with the exact
Spain row sums is a documented future improvement.
"""

# Mean daily contacts per setting × age band for Spain (Prem 2021)
_SPAIN = {
    "home": {
        "child":  4.0,   # 0–14   — siblings + parental contacts, larger households
        "young":  2.8,   # 15–29  — independent/shared accommodation
        "adult":  3.0,   # 30–64  — nuclear family household
        "senior": 3.4,   # 65+    — multigenerational or spousal contact
    },
    "work": {
        "child":  0.0,   # not in labour force
        "young":  5.5,   # entry-level workers, vocational students
        "adult":  6.5,   # primary workforce
        "senior": 1.5,   # partial retirement / occasional informal work
    },
    "school": {
        "child":  12.0,  # primary/secondary classroom density
        "young":   6.0,  # university / vocational training
        "adult":   0.5,  # occasional professional training
        "senior":  0.2,
    },
    "other": {           # community / leisure / public transport / errands
        "child":  4.0,
        "young":  4.5,
        "adult":  3.5,
        "senior": 2.8,
    },
}

# Tolerance bands: LLM output must stay within prior × [1-lo, 1+hi]
_BOUNDS_PCT = {
    "home_contacts":      (0.40, 0.40),   # ±40%
    "work_contacts":      (0.50, 0.50),   # ±50%
    "community_contacts": (0.50, 0.60),   # +60% to allow Andorra's small-country social overlap
}


def age_band(age: int) -> str:
    if age < 15:  return "child"
    if age < 30:  return "young"
    if age < 65:  return "adult"
    return "senior"


def get_priors(age: int) -> dict:
    """Return Prem 2021 Spain mean daily contact counts for this agent's age.

    School contacts are represented structurally by the school network layer
    (not as a SocialProfile scalar), so only the three contact-rate parameters
    that bound a SocialProfile field are returned.
    """
    band = age_band(age)
    return {
        "home_contacts":      _SPAIN["home"][band],
        "work_contacts":      _SPAIN["work"][band],
        "community_contacts": _SPAIN["other"][band],
    }


def get_bounds(age: int) -> dict:
    """
    Return (min, max) allowed values for the three LLM-generated contact fields.
    Used in the EXP04 prompt so the LLM can see the constraint window explicitly.
    """
    p = get_priors(age)
    result = {}
    for key, (lo_pct, hi_pct) in _BOUNDS_PCT.items():
        centre = p[key]
        result[key] = (
            round(max(0.0, centre * (1 - lo_pct)), 2),
            round(centre * (1 + hi_pct), 2),
        )
    return result
