# Pipeline Refactor Plan — V2.2 Regeneration (Realized Households, Full Age Pyramid, Network-First)

Durable spec + status tracker. Update checkboxes as work lands so progress survives interruption.

## Motivation (audit findings, June 2026)

1. **Age-clip bug** ([seeds.py:89](experiments/seeds.py)): `np.clip(rng.normal(midpoint,4),15,85)` floors
   every 0–14 child onto age 15. Config targets 15.2% children (UN WPP 2022); output has **zero under-15**.
2. **Households are fiction**: home cells drawn independently per agent ([generator.py:94](schedules/generator.py));
   "household layer" is res-10 co-location — mean **24.6 agents/cell**, 96% in groups >5, max 430.
3. **No household entities**: `household_composition` is a per-agent string; no linked members.
4. **Wrong ordering**: schedules from independent agents, then "households" inferred from spatial coincidence.
   Literature (Jiang 2022; MATSim) = households → anchors → network → schedules.
5. **4 of 8 social params dead** ([graph_builder.py](networks/graph_builder.py)): `home_contacts`,
   `work_contacts`, `nationality_homophily`, `age_homophily` unused; household layer wrongly uses `workplace_k/p`.
6. **Place-pref ARA regressed** to 0.661 (paper claimed 0.921): calibration not redone when layers grew 15→26.
7. **No school/daycare layer**: Jiang 2022 uses household+work+school+daycare.
8. **Stochastic work anchors**: work destination is a fresh gravity draw per trip — no stable workplace/coworkers.

## Target pipeline order (V2.2)

```
Phase 1   Archetypes (ADULT 15+)                    reuse cached archetypes.json → $0
Phase 2   Expand → adult agents (15+):
            + archetype_id, gender, education, work_sector, work_h3 anchor, employer_id, has_license
Phase 2b  HOUSEHOLD SYNTHESIS (new households.py):
            assemble adults into households per composition; GENERATE children (0-14);
            one shared home_h3; tenure + housing_cost_burden; num_vehicles; parish; school_h3 anchors
Phase 3   SOCIAL NETWORK (moved BEFORE schedules):
            household / workplace(employer) / school / community  — all 8 social params used
Phase 4   SCHEDULES (last): consume home/work/school anchors + network;
            child schedules (school+escort); parenthood β effect; joint/escort trips
Phase 5   Validation + place-pref recalibration (μₖ + Jensen for 26 layers)
```
LLM cost ≈ $0 (reuse archetypes.json + social_profiles.json). New fields are config-grounded, sampled
in expansion — no LLM. CPU ≈ 15 min.

---

## FINALIZED SCHEMA

### Household (NEW first-class entity → households.json)
| field | values | grounding |
|---|---|---|
| household_id | "HH-00001" | — |
| composition | single / couple_no_children / couple_with_children / single_parent / multi_generational / shared_accommodation | existing marginals |
| member_ids | [agent_id…] (adults+children) | — |
| member_roles | {id: head/partner/adult_child/grandparent/child/roommate} | by age+composition |
| size | int | — |
| home_h3 | res-10 cell, SHARED | residential prior (existing home_cell) |
| parish | 1 of 7 | derived from home_h3 lat/lon |
| tenure | owner / renter / social_housing | nat×income prior [SAIG-informed proxy] |
| dwelling_type | apartment / house / shared_flat | size×tenure prior |
| housing_cost_monthly | EUR int | rent_range (renters) / imputed (owners) [config] |
| household_net_income_monthly | EUR int | sum of member income brackets [config wages] |
| housing_cost_burden | float = cost/income | **KEY scenario lever** |
| num_vehicles | int | income×nat car-ownership prior |
| num_children, has_young_children(<6) | int, bool | derived |

### Adult agent (15+) → population.json  (EXISTING fields kept; ADD below)
ADD: `archetype_id` (lineage) · `gender` (M/F, ~50/50 w/ age skew) · `household_id` · `household_role` ·
`education_level` (primary/secondary/tertiary, Eurostat prior by age×nat) · `work_sector` (1 of 7
config sectors | None) · `employer_id` (stable coworker ties | None) · `work_h3` (persistent anchor;
cross-border→border node) · `is_cross_border` (bool) · `has_license` (bool).
KEEP all psychometric/economic/mobility/social/political/place_preferences/goals as-is.

### Child agent (0–14) → population.json (NEW minimal class; NO adult psychometrics)
`agent_id "CH-…"`, `role=child`, `is_minor=true`, `age 0-14`, `gender`, `nationality` (inherit),
`household_id`, `home_h3` (shared), `parish`, `guardian_ids` [adult ids], `school_h3` anchor,
`school_stage` (nursery 0-2 / primary 3-11 / lower_secondary 12-14),
`place_preferences` (child subset: D5 education, D19 daycare, D25 park, D16 recreation, D8 healthcare, D27 outdoor).

### Anchors (persistent, replace stochastic draws)
home_h3 (household) · work_h3 (adult worker) · school_h3 (child). Work/school trips route to the anchor;
only discretionary trips use the gravity model.

### Social network — 4 layers (networks/) — ALL 8 SocialProfile params used
| layer | grouping | params used |
|---|---|---|
| household | realized household members (complete graph) | home_contacts (sizes extra ties), size |
| workplace | shared employer_id | work_contacts, workplace_k, workplace_p |
| school | shared school_h3 (children; + parent–parent school-gate ties) | (NEW) k from school size |
| community | nationality × parish/geography | community_contacts, nationality_homophily, age_homophily, bridging_weight |

### Schedule (schedules/) — ADD
`Trip.accompanied_by: [agent_id]` · `Trip.is_escort: bool` · `Trip.anchor_based: bool`.
Children: school trip to school_h3 + escorted discretionary. Parents: escort children;
parenthood β tightening (Macedo 2026). Adults: work trip to work_h3 anchor (not gravity).

---

## Decisions locked
- Full 0+ population (children as real agents, minimal child schema).
- Regenerate from scratch (reuse cached archetypes.json + social_profiles.json → $0 LLM).
- Realized households with linked members + shared home + tenure/cost-burden + vehicles + parish.
- Adults gain: lineage, gender, education, sector, employer, work anchor, license.
- 4-layer network (add school/daycare); wire all 8 social params.
- Schedules last; anchors for work/school; child + escort + parenthood logic.
- Recalibrate place prefs for 26 layers (μₖ + Jensen).

## Increment checklist
- [x] 1. config priors (folded into expand.py/households.py grounded samplers — no LLM)
- [x] 2. seeds/expand: age within band (children 0–14 real ages); +gender/education/sector/license/archetype_id; child branch
- [x] 3. households.py: synthesis + child placement + shared home + tenure/cost/vehicles/parish + work/school anchors
- [x] 4. child schema (expand.py); NetworkLayers gains school layer
- [x] 5. place_preferences.calibrate_to_reference: logit mean-match → ARA 0.681→0.978 (MDP/SCC/SEF preserved)
- [x] 6. run_population.py reordered (households→network→schedules); reuse cached LLM outputs ($0)
- [x] 7. graph_builder: 4 layers; all 8 social params used; archetype_id lineage lookup
- [x] 8. schedules: child school + escort + parenthood β; anchor-based work/school
- [x] 9. RE-RUN DONE (2111s, $0). FIX: employer_id string-prefix collapse (14 employers) → cell_to_parent(res 9) → 2,063 employers (median 4)
- [x] 10. reconcile paper to V2.2 architecture + numbers (title, abstract, contributions, figure, methodology incl. household synthesis + anchors + 4-layer network + child class + parenthood, all result tables, discussion, limitations, conclusions; Phase→Stage; citations resolve; envs balanced)
- [x] 11. viz chain: route_trips.py + export_to_viz.py paths fixed (app/public/model) + chunked output; routed (0.18% fallback) → 6 chunks (89,998 agents incl 13,679 children)

## V2.2 validated results
- 90,000 = 76,321 adults + 13,679 children (15.2%; was 0% under-15 in V2.1)
- 36,612 households, mean size 2.46; tenure 58% renter / 37% owner / 5% social; burden renters 0.41 vs owners 0.23
- Network (4 layers): household 80,363 (deg 1.79) / workplace 137,124 (deg 3.05) / school 47,087 / community 246,659 = 511,233 edges
- 434,366 trips, 217,183 outbound (+escort 6,854, +child education 13,679)
- Adults: diversity 0.857, coherence 0.387, DA 0.983, norm 0.812, 0 flags
- Place-prefs: ARA 0.978 / MDP 0.929 / SCC 1.000 / SEF 1.000 / composite 0.977
