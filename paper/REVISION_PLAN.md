# Revision Plan — *Andorra Clone Scenario Engine* (major revision)

Target file: `Andorra_paper_mdpi.tex` · Engine: `data/scripts/model/CALCULATOR.py`
Status: **in progress** · Decision: Major Revision (R1 harsh, R2 confused, R3 positive — none reject)

This plan **merges** two threads: (1) the reviewer-driven manuscript revision, and
(2) the engine upgrade toward "sovereign decision infrastructure." They are the same
gap from two sides: the provenance refactor *is* the R1.4 fix; the policy-instrument
layer *is* the R1.1/R3.1/R1.5 fix.

---

## Locked decisions (defaults — change if wrong)
- **Title:** drop "Digital Twin" → *"The Andorra Clone Scenario Engine: A Data-Grounded Framework for Policy-Oriented National Development Planning."* Reposition DT as "an upstream, auditable layer toward a national digital twin." ✅ applied
- **Inversion benchmark:** YES — population-driven vs GDP-driven back-cast on 2010–2024.
- **Spatial:** full subsection (Urban Science angle), using existing GeoJSON assets.
- **Policy layer:** include a *light* version in Paper 1 (3–4 instruments, worked example). Heavy non-linear/feedback + agents → Paper 2.
- **Journal:** ✅ **Urban Science (MDPI).** `\documentclass` option set to `urbansci` — verify it compiles on Overleaf (the `Definitions/` class folder is not in the repo).

---

## Phase A — Reframe & restructure (writing, no model runs) ~2–3 days
Flips R2 from "can't review" to "clear"; neutralizes framing half of R1.1/R1.6/R3.1; clears R2 + R3.6.

- [x] **Title** — drop Digital Twin, reposition (R1.1/R3.1)
- [x] **Abstract** — soften DT, clarify contribution & findings, add policy framing (R2.1) *(numbers pass again in Phase D)*
- [x] **Intro framing** — explicit "what we built / what's new", practical vs scientific contribution split, RQ1–RQ3, paper outline (R2.2/R2.4/R1.6)
- [x] **Methodology reframe** — engine restated as research *result*; 5-stage "how it was developed"; 4-class relationship/provenance taxonomy introduced (R2.4/R1.4)
- [x] **Contribution vs scenario-tool** — added subsection "Positioning: Scenario Engine, Digital Twin, or DSS?" answering R3.1(a)(b)(c) + R1.1
- [x] **Related Work** — added subsection "AI- and Agent-Based Approaches" pulling forward generative-agent refs (R2.3)
- [x] **Trim Next Steps** — cut from ~22 lines to a focused paragraph; agent layer → follow-up study (R3.6)

**→ Phase A complete.** Open Phase-A debt for Phase B: methodology now *promises* a `tab:provenance` table (B1) and a policy-lever mapping (B5) — both must be delivered there. See `% TODO(B1)` marker in the Methodology section.

## Phase B — Engine work + evidence (model runs) ~4–6 days
The core of R1's "must improve." All re-runs of `CALCULATOR.py`.

Harness: `data/scripts/model/phaseB_analysis.py` → `phaseB_results.json`. All numbers below are live runs; harness reproduces the paper's 2049 Continuity Pop=117,666 exactly.

- [x] **B1 — Provenance refactor + table.** Parameterized hardcoded tourism/afford constants in `step_next`; added `tab:provenance` (Identity/Calibrated/Literature/Expert/Stabilizing) to reproducibility subsection. (R1.4/R3.3)
- [x] **B2 — Sensitivity analysis.** `tab:sensitivity` added. Key finding: β₁ dominant (±12–14% Pop); afford **threshold** load-bearing & asymmetric (−31%); β_afford inert (±0.1%); tourism params decoupled from Pop. (R1.4/R3.3)
- [x] **B3 — Multi-series validation.** `tab:validation` added: NatCov 0.25%, LE 1.0%, Afford 5.7%, Pop 9.1%, Salary 10.5%, WLB 10.8%, CO2pc 11.9%. (R3.2)
- [x] **B4 — Inversion benchmark.** `tab:benchmark` added + **honest reframe**: inverted 9.1% loses to linear trend 1.7%; even fitted β floors at 7.45%. Demoted to structural/policy claim; softened two-regime claim; corrected ±18k→−14.1k/+15.9k. (R1.2/R3.5)
- [x] **B5 — Policy-instrument layer.** Added `apply_policy()` + `tour_demand_mult` hook in `CALCULATOR.py`; `tab:policy` (catalog) + `tab:policy_demo` (managed-growth worked example) in Methodology. (R1.1/R1.5/R3.1)
- [x] **B6 — Scenario-parameter justification.** Justified 6.0% TFP as stress value (~7× calibrated rate) vs microstate envelope. (R1.3)

## Phase C — Results & spatial ✅ COMPLETE
- [x] **Binding-constraints reframe** — `subsec:constraints` + `tab:constraints`: affordability brake binds 2025 (all growth paths, never Degrowth); tourism cap 2026–2030. Honestly excluded mechanical beds + placeholder water-security. (R1.5/R3.4)
- [x] **Spatial subsection** — `subsec:spatial` + `tab:spatial` + `fig:spatial` (4-panel map, `paper/spatial_growth_2049.png`): Density 0 new cells (infill), Overgrowth 1,083 new (sprawl), Degrowth 3,745 contracting (periphery). Real H3 suitability allocation. (R3.7)
- [x] Honesty: spatial-layer limitation added (separate module, approx totals); fixed both "original 2049" copyedit leftovers.
- Figure regenerable via `data/scripts/model/generate_spatial_figure.py`. **Upload `spatial_growth_2049.png` to Overleaf root.**

## Phase D — Response + polish
- [ ] Point-by-point **response-to-reviewers letter** (every comment → change + line ref)
- [ ] Update `cover_letter.tex`
- [ ] Copyedit: fix "original 2049 projection" leftover (horizon-change residue); **confirm journal + `\documentclass` option**
- [ ] Abstract numbers pass (incorporate validation/benchmark results)

---

## Target engine architecture (folds into B1/B5)
```
POLICY LAYER (new)   permit cap · immigration quota · tourism tax/quota · social-housing · renewable mandate
   ↓ cited transmission map → params/exog
DRIVER LAYER         exogenous GDPpc path · tourism driver
   ↓
BEHAVIORAL LAYER     estimated elasticities: GDP→migration · income→price · afford→brake · tourism logistic
   ↓
IDENTITY LAYER       accounting: infra = pop×ratio · CO₂ = pc×pop · water = pop×pc   (NOT "assumptions")
   ↓
CONSTRAINT LAYER     feasibility clamps — flagged, never silent
```
**Discipline rule:** no new parameter unless it is (a) estimable from data, or (b) a real, citable policy lever. Otherwise it is just new R1.4 ammunition.

Injection points already exist: `step_next` reads `state`/`params`/`exog`; `LandProtect` is a working policy lever (proof of concept). → This is an **extension, not a rewrite.**

### First policy instruments to spec (B5)
| Instrument | Transmission → model variable | Existing hook |
|---|---|---|
| Construction-permit cap | caps `Permits` inflow → building stock `B` | `Perm_phi*`, `LandProtect` ✅ |
| Immigration quota | caps endogenous `Pop_next` inflow | `pop_elasticity_factor`, `force_pop` |
| Tourism tax / quota | lowers effective arrivals vs logistic cap | `Tour_cap`, friction term |
| Social-housing injection | shifts `Afford` ratio → migration brake | `beta_afford`, `H_h*` |

---

## Three-paper program (confirmed)
Two halves: **quantitative/macro** (Papers 1–2) and **behavioural/micro** (Paper 3, the 90k full-population agent model).
- **Paper 1 (this revision):** systems/method paper — transparent policy→KPI engine, broad, validated. = Phase A + B1–B6 + C.
- **Paper 2:** empirical-mechanism paper — policy/labour-driven migration model; 9% elasticity back-cast is the explicit baseline-to-beat; microstate panel. *Gate: depends on immigration-by-permit + policy-event data existing — verify before committing (else fold into 2 papers).*
- **Paper 3:** behavioural/emotional 90k-agent society under scenarios (`Andorra_agents_paper_*.tex` + `viz-abm-emotion-main`).

Boundary discipline: Paper 1 treats population→policy at *elasticity* resolution (coarse, honest); Paper 2 owns the *mechanism*. Paper 2 = aggregate migration flows; Paper 3 = individual agents (micro-foundation of those flows).

## Reviewer coverage (compact)
R1.1/R3.1 → A(title/abstract/contrib subsec)+B5 · R1.2/R3.5 → B4 · R1.3 → B6 · R1.4/R3.3 → B1+B2 ·
R1.5/R3.4 → C · R1.6/R2.4 → A(intro/methodology) · R2.1 → A(abstract) · R2.2 → A(RQ/outline) ·
R2.3 → A(related work) · R3.2 → B3 · R3.6 → A(trim) · R3.7 → C(spatial)
