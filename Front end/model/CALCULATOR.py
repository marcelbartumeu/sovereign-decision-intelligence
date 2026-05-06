import json
import math
import random
from copy import deepcopy
from pathlib import Path

# ========== infrastructure layer (electricity, water, hospitals, schools, roads) ==========
INFRASTRUCTURE_CONFIG = {
    # Baseline population (2024)
    "P0": 87097,
    
    # Scenario populations
    # Note: CO (Continuity) is not included here because CALCULATOR.py always overrides
    # it with the actual population value each year. These defaults are for standalone testing only.
    "populations": {
        "OG": 200000,   # Overgrowth
        "DG": 50000,    # Degrowth
        "DN": 170000    # Density (Barcelona-like, no building expansion)
    },

    # Electricity constants
    "electricity": {
        "e_pc_0": 3000,  # kWh/person/year (baseline)
        "f_E": {
            "OG": 1.0,
            "CO": 1.0,
            "DG": 1.0,
            "DN": 1.0
        },
        "CF": 0.5,  # capacity factor
        "H": 8760,  # hours/year
        "r": {  # renewable CAPACITY share (installed capacity fraction that is renewable)
            # Andorra's grid is hydro-dominated (93.1% renewable energy, 2024).
            # With hydro CF ~0.38 and fossil backup CF ~0.25, achieving 93% energy
            # share requires ~88% of installed capacity to be renewable.
            # Source: IEA/Andorcel grid data; calibrated to match 2024 Ren=0.931.
            "OG": 0.70,   # Growth strains grid → more fossil/import backup
            "CO": 0.88,   # Continuity: reflects Andorra's actual hydro-dominant grid
            "DG": 0.88,   # Degrowth: maintains renewable capacity, lower total demand
            "DN": 0.90    # Density: compact & efficient → highest renewable share
        }
    },
    
    # Water constants
    "water": {
        "w_pc": 150,  # L/person/day
        "alpha": 0.12,  # household share of total water use
        "Y_safe": 10000000  # m³/year (placeholder - should be configured)
    },
    
    # Hospital constants
    "hospitals": {
        "b0": 2.5,  # beds per 1000 people (baseline)
        "bedsPer1000": {
            "OG": 2.5,
            "CO": 2.5,
            "DG": 2.5,
            "DN": 2.5
        }
    },
    
    # School constants
    "schools": {
        "S0": 11259,  # baseline students (2024 actual data)
        "studentsPerClassroom": 25,
        "studentsPerSchool": 500
    },
    
    # Road constants
    "roads": {
        "L0": 269  # km total roads (baseline)
    }
}


def computeInfrastructureScenario(scenario, config=None):
    """
    Compute infrastructure requirements for a given scenario.
    
    Args:
        scenario: One of "OG" (Overgrowth), "CO" (Continuity), "DG" (Degrowth), "DN" (Density)
        config: Optional configuration dict. If None, uses INFRASTRUCTURE_CONFIG.
    
    Returns:
        Dictionary with infrastructure calculations for the scenario.
    """
    if config is None:
        config = INFRASTRUCTURE_CONFIG
    
    # Validate scenario
    if scenario not in ["OG", "CO", "DG", "DN"]:
        raise ValueError(f"Invalid scenario: {scenario}. Must be 'OG', 'CO', 'DG', or 'DN'")

    # Get population for scenario
    # Handle missing CO population (use baseline as placeholder for standalone testing)
    if scenario == "CO" and "CO" not in config.get("populations", {}):
        P_s = config["P0"]  # Use baseline as placeholder
    else:
        P_s = config["populations"][scenario]
    P0 = config["P0"]

    # ========== Electricity Calculations ==========
    e_pc_0 = config["electricity"]["e_pc_0"]
    f_E = config["electricity"]["f_E"][scenario]
    CF = config["electricity"]["CF"]
    H = config["electricity"]["H"]
    r = config["electricity"]["r"][scenario]

    e_pc_s = e_pc_0 * f_E
    E_s = P_s * e_pc_s  # kWh/year
    C_s = E_s / (CF * H)  # kW
    C_RE_s = r * C_s  # renewable capacity
    C_FOSS_s = (1 - r) * C_s  # fossil capacity

    # ========== Water Calculations ==========
    w_pc = config["water"]["w_pc"]
    alpha = config["water"]["alpha"]
    Y_safe = config["water"]["Y_safe"]

    W_hh_s = P_s * w_pc * 365 / 1000  # m³/year (household demand)
    W_tot_s = W_hh_s / alpha  # m³/year (total demand)
    I_W_s = Y_safe / W_tot_s if W_tot_s > 0 else 0  # water security index

    # ========== Hospital Calculations ==========
    b0 = config["hospitals"]["b0"]
    bedsPer1000 = config["hospitals"]["bedsPer1000"][scenario]

    B0 = (b0 / 1000) * P0  # baseline beds
    B_req_s = (bedsPer1000 / 1000) * P_s  # required beds for scenario
    B_delta_s = B_req_s - B0  # change in beds needed

    # ========== School Calculations ==========
    S0 = config["schools"]["S0"]
    studentsPerClassroom = config["schools"]["studentsPerClassroom"]
    studentsPerSchool = config["schools"]["studentsPerSchool"]

    r_stu = S0 / P0 if P0 > 0 else 0  # student share
    S_s = r_stu * P_s  # students in scenario
    classrooms_s = S_s / studentsPerClassroom if studentsPerClassroom > 0 else 0
    schools_s = S_s / studentsPerSchool if studentsPerSchool > 0 else 0

    # ========== Road Calculations ==========
    L0 = config["roads"]["L0"]

    l_s = L0 / P_s if P_s > 0 else 0  # km/person
    perCapita_m_s = l_s * 1000  # m/person

    # ========== Return structured result ==========
    return {
        "scenario": scenario,
        "population": P_s,
        "electricity": {
            "perCapita_kWh_year": e_pc_s,
            "demand_kWh_year": E_s,
            "capacity_kW": C_s,
            "renewableCapacity_kW": C_RE_s,
            "fossilCapacity_kW": C_FOSS_s
        },
        "water": {
            "perCapita_L_day": w_pc,
            "householdDemand_m3_year": W_hh_s,
            "totalDemand_m3_year": W_tot_s,
            "waterSecurityIndex": I_W_s
        },
        "hospitals": {
            "baselineBeds": B0,
            "requiredBeds": B_req_s,
            "deltaBeds": B_delta_s
        },
        "schools": {
            "students": S_s,
            "classrooms": classrooms_s,
            "schools": schools_s
        },
        "roads": {
            "totalLength_km": L0,
            "perCapita_m": perCapita_m_s
        }
    }


def computeAllInfrastructureScenarios(config=None):
    """
    Compute infrastructure requirements for all scenarios.
    
    Args:
        config: Optional configuration dict. If None, uses INFRASTRUCTURE_CONFIG.
        Note: If CO (Continuity) is not in config["populations"], uses P0 (baseline) as placeholder.
    
    Returns:
        Dictionary with keys "OG", "CO", "DG" containing infrastructure calculations.
    """
    if config is None:
        config = INFRASTRUCTURE_CONFIG

    # Handle missing CO population (use baseline as placeholder for standalone testing)
    if "CO" not in config.get("populations", {}):
        config = config.copy()
        config["populations"] = config.get("populations", {}).copy()
        config["populations"]["CO"] = config["P0"]  # Use baseline as placeholder

    scenarios = ["OG", "CO", "DG"]
    results = {}

    for scenario in scenarios:
        results[scenario] = computeInfrastructureScenario(scenario, config)

    return results


# ========== utilities ==========
def clamp(x, a, b): return max(a, min(b, x))
def growth(curr, prev): return 0.0 if prev == 0 else (curr - prev) / prev

def get(d, key, default):
    v = d.get(key, default)
    return default if v is None else v

def interp_linear(y0, yT, t, T):
    """Linear path from y0 to yT over T steps; t = 1..T."""
    return y0 + (yT - y0) * (t / T)

# ========== one-step model (unchanged except we pass exog per year) ==========
def step_next(baseline):
    S = deepcopy(baseline.get("state", {}))
    P = baseline.get("params", {})
    X = baseline.get("exog", {})

    def p(name, default): return get(P, name, default)
    def s(name, default): return get(S, name, default)
    def x(name, default): return get(X, name, default)

    Pop_t  = s("Pop", 0)
    GDPpc_t = s("GDPpc", 0)
    Emp_t  = clamp(s("Emp", 0.95), 0, 1)
    HPrice_t = s("HPrice", 0)
    Tour_t = s("Tour", 0)
    B_t    = s("B", 0)
    FB_t   = s("ForeignBorn", 0)
    LE_t   = s("LE", 85.0)
    WLB_t  = clamp(s("WLB", 0.5), 0, 1)
    Access_t = clamp(s("Access", 0.8), 0, 1)
    Income_t = s("Income", 0)  # Median household income (annual)
    Salary_t = s("Salary", 0)
    Afford_t = s("Afford", 0)
    NatCov_t = clamp(s("NatCov", 0.7), 0, 1)
    CO2pc_t  = s("CO2pc", 0)
    Ren_t    = clamp(s("Ren", 0.3), 0, 1)
    AQI_t    = s("AQI", 40.0)
    Water_t  = s("Water", 0.0)
    Temp_t   = s("Temp", 12.0)

    Beds_t = s("Beds", 0)
    PriceIdx_t = s("PriceIdx", 1.0)
    GlobalTravel_t = s("GlobalTravel", 1.0)
    LaborShare_t = s("LaborShare", 0.55)
    Rate_t = s("Rate", 0.03)
    TourHomeDemand_t = s("TourHomeDemand", 0.0)
    GDP_t = s("GDP", GDPpc_t * Pop_t)
    BusinessFormation_t = s("BusinessFormation", 1450)
    Marriages_t = s("Marriages", 438)
    Divorces_t = s("Divorces", 13)
    FamilyStability_t = s("FamilyStability", 0.0296803653)

    # GDPpc lag values for the research-based population model
    # (Andorra 2024 → 2023: +3.8%; 2023 → 2022: +9.6% — IMF/MacroTrends)
    GDPpc_prev  = s("GDPpc_prev",  GDPpc_t / 1.038)
    GDPpc_prev2 = s("GDPpc_prev2", GDPpc_t / 1.038 / 1.096)

    # exogenous/forced levels for this step (already interpolated upstream)
    Pop_target   = x("Pop_target",   Pop_t)
    Tour_target  = x("Tour_target",  Tour_t)
    B_target     = x("B_target",     B_t)
    GDPpc_target = x("GDPpc_target", None)
    force_pop    = x("force_pop",    False)   # population is now endogenous (GDP-driven)
    force_gdp    = x("force_gdp",    False)   # GDP per capita is the exogenous lever
    force_tour   = x("force_tour",   True)
    force_build  = x("force_build",  True)

    Pop_t1  = Pop_target if force_pop else Pop_t
    Tour_t1 = Tour_target if force_tour else Tour_t
    B_t1    = B_target if force_build else B_t

    # P4 — Tourism capacity constraint (logistic ceiling).
    # Carrying capacity is anchored to 2024 sustainable load (9,646,656 visitors at 85%
    # utilization) and scaled by building stock (B^0.4, proxy for accommodation/service
    # capacity) and resident population (Pop^0.2, proxy for service workforce).
    # When utilization > 85%, each extra visitor faces exponentially rising friction:
    #   Tour_constrained = cap×0.85 + excess × exp(−3 × excess_fraction)
    # This implements Butler (1980) TALC saturation phase; elasticity from
    # Peeters et al. (2019) Tourism Management 72:48–56.
    Tour_cap = (9646656.0 / 0.85) * ((B_t1 / 10645.0) ** 0.4) * ((Pop_t1 / 87097.0) ** 0.2)
    if Tour_cap > 0:
        _util = Tour_t1 / Tour_cap
        if _util > 0.85:
            _excess = _util - 0.85
            Tour_t1 = Tour_cap * 0.85 + (Tour_t1 - Tour_cap * 0.85) * math.exp(-3.0 * _excess)
            Tour_t1 = max(0.0, Tour_t1)

    # ── Research-based GDP → Population model ──────────────────────────────────
    # Methodology: IMF 2025 Andorra Selected Issues + World Bank historical data.
    # Causal chain: GDP growth → labour demand → immigration permits → new residents.
    # Empirical elasticity ≈ 0.4–0.6 pp population growth per 1 pp GDP growth (1–2 yr lag).
    # Formula: ΔPop_t = −0.1%/yr (natural change) + 0.40×gGDP_{t-1} + 0.10×gGDP_{t-2}
    # Housing-affordability constraint suppresses migration when cost > 30% of income
    # (Sá 2015, J Urban Econ 88:66–87; Diamond 2016, AER 106:590–632; IMF 2025 housing paper).

    # GDP growth rates at the two lags (computed from stored state)
    gGDPpc_lag1 = growth(GDPpc_t, GDPpc_prev)     # growth from t-1 to t
    gGDPpc_lag2 = growth(GDPpc_prev, GDPpc_prev2)  # growth from t-2 to t-1
    gHPrice     = growth(HPrice_t, s("HPrice_prev", HPrice_t))

    # Elasticity coefficients (scenario-adjustable via pop_elasticity_factor)
    pop_elasticity_factor = p("pop_elasticity_factor", 1.0)
    beta_lag1 = p("beta_gdp_lag1", 0.40) * pop_elasticity_factor
    beta_lag2 = p("beta_gdp_lag2", 0.10) * pop_elasticity_factor

    # Housing-affordability migration feedback
    beta_afford = p("beta_afford", 0.10)
    afford_migration_effect = -beta_afford * max(0.0, Afford_t / 100.0 - 0.30) * Pop_t

    # Natural demographic change: −0.1%/yr (deaths > births in Andorra; fertility ~0.8–1.5)
    gnat = p("gnat", -0.001)

    Pop_model = (Pop_t * (1 + gnat + beta_lag1 * gGDPpc_lag1 + beta_lag2 * gGDPpc_lag2)
                 + afford_migration_effect)
    Pop_next = Pop_t1 if force_pop else Pop_model

    NetMig = Pop_next - Pop_t
    alpha_fb = x("alpha_fb", p("alpha_fb", 1.0))
    current_year = S.get("Year", 2024)

    # Foreign-born: model net migration in normal steps; in the first future year (2024->2025)
    # use continuity of demographic composition (foreign-born share) so the transition is
    # scientifically consistent with 2024 baseline rather than a one-year jump.
    if current_year == 2024 and Pop_t > 0:
        sFB_t = FB_t / Pop_t
        FB_next = sFB_t * Pop_next  # share constant in first year
        sFB_next = sFB_t
    else:
        FB_next = FB_t + alpha_fb * max(NetMig, 0.0)
        if NetMig < 0:
            FB_next = max(0.0, FB_t + NetMig)
        sFB_next = 0.0 if Pop_next <= 0 else FB_next / Pop_next

    # Access to Health (realistic scenario-dependent calculation)
    # Base access to health from 2024 data (0.922 = 92.2%)
    base_access = 0.922

    # Economic prosperity factor: higher GDPpc → better healthcare access.
    # Reference = 2024 actual GDPpc (42,852.96). Each full baseline-unit gain adds +5 pp.
    economic_factor = (GDPpc_t - 42852.96) / 42852.96 * 0.05

    # Population density factor (more people = potential strain on healthcare)
    density_factor = max(-0.05, (Pop_next - 87097.0) / 87097.0 * -0.02)  # Population pressure

    # Tourism factor: normalized to 2024 actual tourism (9,646,656).
    # Tourism expands tax base (+) but also strains ER capacity (−); net effect small.
    tourism_factor = (Tour_t1 - 9646656.0) / 9646656.0 * 0.01

    # Employment factor (higher employment = better social security and healthcare access)
    employment_factor = (Emp_t - 0.95) * 0.1  # Employment impact on healthcare access

    # Calculate access to health with realistic scenario adjustments
    Access_next = clamp(base_access + economic_factor + density_factor + tourism_factor + employment_factor, 0.7, 0.98)
    
    # Health capacity (for consistency with model structure)
    HealthCap_next = Access_next * Pop_next * 0.01  # Health capacity scales with access and population

    # Life Expectancy (will be calculated later after GDPpc_next is computed)

    # Work–Life Balance (will be calculated later after Income is computed)

    # GDP per Capita (recompute after employment)
    gTFP = get(baseline.get("exog", {}), "gTFP", p("gTFP", 0.01))
    gamma1 = p("GDPpc_gamma1", 0.3); gamma2 = p("GDPpc_gamma2", 0.1)
    gTour = growth(Tour_t1, Tour_t) if Tour_t > 0 else 0.0
    GDPpc_prov = GDPpc_t * (1 + gTFP + gamma1 * 0.0 + gamma2 * gTour)

    # Employment rate: state-anchored using ANNUAL (year-over-year) incremental changes.
    # Using cumulative deviations from 2024 compounded the deficit each year, producing
    # unrealistically low employment in Degrowth (86%) while Andorra has never dipped
    # below 94% historically (2010–2024). Annual deltas prevent this artefact.

    # Economic growth: annual GDP per capita change (positive growth → more jobs)
    gGDPpc_prov = growth(GDPpc_prov, GDPpc_t)
    economic_emp_factor = gGDPpc_prov * 0.1

    # Population growth: rapid in-migration → mild employment dilution (annual change)
    pop_growth = growth(Pop_next, Pop_t) if Pop_t > 0 else 0.0
    pop_growth_factor = pop_growth * -0.05        # faster growth → slight dilution

    # Tourism growth: more tourism → more jobs (annual change)
    tour_growth = growth(Tour_t1, Tour_t) if Tour_t > 0 else 0.0
    tour_emp_factor = tour_growth * 0.02

    Emp_next = clamp(Emp_t + economic_emp_factor + pop_growth_factor + tour_emp_factor, 0.85, 0.98)

    # Employment calculation is now done above

    dEmp = Emp_next - Emp_t
    GDPpc_next = GDPpc_t * (1 + gTFP + gamma1 * dEmp + gamma2 * gTour)

    # GDP forcing: scenario supplies the interpolated GDPpc path as the exogenous driver
    if force_gdp and GDPpc_target is not None:
        GDPpc_next = float(GDPpc_target)

    # Life Expectancy
    # Base = 2024 actual (84.5 years; Govern d'Andorra / WHO).
    base_LE = 84.5

    # Economic prosperity: reference = 2024 actual GDPpc (42,852.96).
    # Each full doubling of income adds ~2 years LE (Preston curve; empirical range 1–3 yr).
    economic_boost = (GDPpc_next - 42852.96) / 42852.96 * 2.0

    # Population growth strain on healthcare system (crowding effect).
    health_strain = max(0, (Pop_next - 87097.0) / 87097.0 * 1.0)

    # Air quality (PM2.5, μg/m³): NOT EPA AQI. WHO AQG 2021: 5 μg/m³ annual mean.
    # EU interim target 1 = 10 μg/m³. Epidemiology: each 10 μg/m³ change ≈ ±0.6 yr LE
    # (Pope et al. 2009, Lancet; WHO Global Health Risks 2009).
    # Formula: compare to 10 μg/m³ reference at 0.06 yr per μg/m³.
    # At 2024 baseline (8.40 μg/m³): (10-8.40)*0.06 = +0.096 yr (small benefit vs reference).
    environmental_impact = clamp((10.0 - AQI_t) * 0.06, -1.5, 1.5)

    # NOTE: tourism_impact REMOVED — no peer-reviewed basis for direct tourism → LE effect.
    # Tourism GDP effects are captured via economic_boost through GDPpc_next.

    LE_next = clamp(base_LE + economic_boost - health_strain + environmental_impact, 75, 90)

    # Income & Salary (realistic relationship to GDP)
    a0 = p("Income_a0", 0.0); a1 = p("Income_a1", 0.6); a2 = p("Income_a2", 0.0)
    Income_next = a0 + a1 * GDPpc_next + a2 * Emp_next

    # Salary calculation (consistent with income growth)
    # Base salary-to-income ratio from 2024: 30,852 / 55,534 = 0.556
    salary_ratio = p("Salary_ratio", 0.556)  # Salary-to-income ratio
    # Salary is monthly (like historical data: 2,571 per month)
    # Income is annual, so convert: Salary_monthly = (Salary_ratio * Income_annual) / 12
    Salary_next = (salary_ratio * Income_next) / 12.0

    # Work–Life Balance
    # State-anchored: evolves from WLB_t using ANNUAL (year-over-year) incremental changes.
    # Using cumulative deviations from 2024 would compound the effect each year and
    # produce unrealistic endpoint values in high-growth scenarios.
    # NOTE: Andorra WLB is an extrapolation from Spain/France indices (no Andorra-specific
    # Andorran data exist). Series shows a linear decline 0.64→0.625 (2010–2024).
    # Treat absolute level as indicative; directional trends are meaningful.

    # Income effect: year-over-year income growth → modest WLB improvement
    economic_factor = growth(Income_next, Income_t) * 0.1

    # Population density effect: rapid population growth adds work pressure (annual change)
    pop_growth = growth(Pop_next, Pop_t) if Pop_t > 0 else 0.0
    density_factor = max(-0.03, pop_growth * -0.05)

    # Tourism intensity: seasonal & service jobs reduce WLB (annual tourism growth)
    tour_growth = growth(Tour_t1, Tour_t) if Tour_t > 0 else 0.0
    tourism_factor = max(-0.02, tour_growth * -0.05)

    # Employment rate effect: very high employment → overwork conditions
    employment_factor = (Emp_next - 0.95) * 0.2

    WLB_next = clamp(WLB_t + economic_factor + density_factor + tourism_factor + employment_factor, 0.3, 0.8)

    # Business Formation (scales with population and economic conditions)
    # Base business formation per capita from 2024 data
    base_business_per_capita = 1450.0 / 87097.0  # ~0.0166 businesses per person
    
    # Scale with population (more people = more businesses)
    pop_scaling = Pop_next / 87097.0  # Scale relative to 2024 population

    # Economic growth factor: reference = 2024 actual GDPpc (42,852.96)
    gdp_scaling = GDPpc_next / 42852.96

    # Tourism factor: reference = 2024 actual (9,646,656)
    tour_scaling = Tour_t1 / 9646656.0
    
    # Combine factors with weights
    BusinessFormation_next = 1450.0 * pop_scaling * (0.7 + 0.2 * gdp_scaling + 0.1 * tour_scaling)

    # Family Stability Proxy — computed as divorces / marriages, matching the exact
    # definition used for all historical values in Current.json (verified 2010–2023).
    # Lower ratio = fewer divorces per marriage = more stable. Historical range: 0.10–0.53.
    #
    # 2024 raw divorces = 13 (confirmed outlier; likely incomplete annual reporting).
    # → The transform_data function loads Divorces_annual_avg = 98.2 (2010–2024 mean).
    # → base_divorces below uses that average, not the 13-divorce outlier.
    #
    # NOTE: anchoring the prior formula to base_stability=0.0297 (the 2024 outlier ratio)
    # produced near-zero family stability across ALL scenarios regardless of context —
    # a clear artifact. This version removes that anchor entirely.

    base_marriages = 438       # 2024 actual (Govern d'Andorra)
    base_divorces = s("Divorces_annual_avg", 98.2)  # 2010–2024 multi-year average

    # Marriages: scale with population and modest GDP prosperity effect
    marriage_rate = base_marriages / 87097.0
    Marriages_next = max(1, int(round(marriage_rate * Pop_next * (0.8 + 0.2 * gdp_scaling))))

    # Divorces: scale with population using the long-run average rate
    divorce_rate = base_divorces / 87097.0
    Divorces_next = max(0, int(round(divorce_rate * Pop_next)))

    # Stability proxy = divorce-to-marriage ratio (directly mirrors historical definition)
    FamilyStability_next = clamp(
        Divorces_next / Marriages_next if Marriages_next > 0 else 0.225,
        0.0, 1.0
    )

    # Buildings - Formula-based calculation
    delta_demo = p("B_delta", 0.01)
    if force_build:
        B_next = B_t1

    else:
        # Get permit parameters
        phi0 = p("Perm_phi0", 0.0); phi1 = p("Perm_phi1", 0.0); phi2 = p("Perm_phi2", 0.0); phi3 = p("Perm_phi3", 0.0)
        LandProtect = get(baseline.get("exog", {}), "LandProtect", p("LandProtect", 0.0))
        
        # Calculate permits based on:
        # - Base permit rate (phi0)
        # - Population growth sensitivity (phi1)
        # - Housing price growth sensitivity (phi2)
        # - Land protection policies (phi3)
        pop_growth_rate = growth(Pop_next, Pop_t) if Pop_t > 0 else 0.0
        hprice_prev = get(S, "HPrice_prev", HPrice_t)
        hprice_growth_rate = growth(HPrice_t, hprice_prev) if hprice_prev > 0 else 0.0
        
        Permits = phi0 + phi1 * pop_growth_rate + phi2 * hprice_growth_rate - phi3 * LandProtect
        
        # Ensure permits are non-negative (can't have negative building permits)
        Permits = max(0.0, Permits)
        
        # Calculate next year's buildings: current + new permits - demolitions
        B_next = B_t + Permits - delta_demo * B_t
        
        # Ensure buildings don't go below a minimum threshold (at least 50% of initial)
        B_min = get(baseline.get("state", {}), "B", B_t) * 0.5
        B_next = max(B_min, B_next)

    # Housing & Affordability (realistic calculation)
    # Formula produces annual-scale cost; we store monthly to match dashboard and historical (unit: €/month)
    h0 = p("H_h0", 0.0); h1 = p("H_h1", 0.3); h2 = p("H_h2", 1.5); h3 = p("H_h3", 1.0); h4 = p("H_h4", 0.8)
    HPrice_next_annual = h0 + h1 * Income_next - h2 * (B_next / max(Pop_next, 1)) - h3 * s("Rate", 0.03) + h4 * s("TourHomeDemand", 0.0)
    HPrice_next = HPrice_next_annual / 12.0  # Store monthly (dashboard and historical use €/month)
    
    # Housing affordability as percentage of median household income spent on housing
    # Based on corrected data: 2024 = 28.79843554
    base_afford = 28.79843554  # 2024 baseline (corrected data)
    
    if Income_next > 0 and HPrice_next > 0:
        monthly_income = Income_next / 12
        monthly_housing_cost = HPrice_next  # Already monthly
        Afford_next = min(60.0, (monthly_housing_cost / monthly_income) * 100.0)  # Cap at 60%
    else:
        Afford_next = base_afford

    # Natural coverage (based on Andorra's verified 2024 NatCov = 0.9307)
    # Andorra total area: 468 km² (official). Buildable: 65.41 km².
    # Calibration: (1 - 0.9307) × 468 = 32.43 km² constructed → 10,645 / 32.43 = 328.2 bldg/km².
    # The prior value (344.1) used only the dense built-up footprint (30.9 km²) and therefore
    # under-counted total impervious surface (roads, car parks, infrastructure), producing
    # NatCov ≈ 0.934 vs the official 0.9307. 328.2 exactly reproduces the 2024 baseline.

    total_area = 468.0   # km² (official Andorra territory)
    buildable_area = 65.41  # km² (government land-use plan)
    buildings_per_km2 = 328.2  # calibrated to NatCov 2024 = 0.9307 (see above)
    
    # Calculate constructed area based on number of buildings
    constructed_area = B_next / buildings_per_km2
    
    # Ensure constructed area doesn't exceed buildable area
    constructed_area = min(constructed_area, buildable_area)
    
    # Calculate natural coverage
    natural_area = total_area - constructed_area
    NatCov_next = natural_area / total_area
    
    # Calculate dUrban for biodiversity calculation
    dB = B_next - B_t
    phi_fp = p("phi_fp", 1.0/500.0)
    dUrban = phi_fp * dB

    # Total CO2 emissions for the country (realistic calculation with density effects)
    # Base total CO2 from 2024 data: 470 KT = 470,000 tons CO2
    base_total_co2 = 470000.0  # 470 KT = 470,000 tons CO2
    
    # Calculate population density effects on efficiency
    # Higher density = more efficient per capita (shared infrastructure, economies of scale)
    # Lower density = less efficient per capita (more individual transportation, less shared resources)
    
    base_density = 87097.0 / 468.0  # people per km² (2024)
    current_density = Pop_next / 468.0  # people per km² (future)
    density_ratio = current_density / base_density
    
    # Density efficiency factor: higher density = lower per capita emissions
    # Overgrowth (high density) → lower per capita emissions
    # Degrowth (low density) → higher per capita emissions
    density_efficiency = 1.0 - 0.3 * (density_ratio - 1.0)  # 30% efficiency gain per density doubling
    density_efficiency = max(0.6, min(1.4, density_efficiency))  # Clamp between 60% and 140%
    
    # Economic scaling: reference = 2024 actual GDPpc (42,852.96)
    economic_scaling = GDPpc_next / 42852.96

    # Tourism impact (minimal): reference = 2024 actual (9,646,656)
    tour_scaling = Tour_t1 / 9646656.0
    tour_factor = 1.0 + 0.01 * (tour_scaling - 1.0)  # 1% impact from tourism changes
    
    # Calculate per capita CO2 with density effects
    base_co2pc = base_total_co2 / 87097.0  # 5.396 tons per capita (2024)
    CO2pc_next = base_co2pc * economic_scaling * density_efficiency * tour_factor
    
    # Total CO2 = per capita * population
    CO2_total_next = CO2pc_next * Pop_next

    # Renewables (realistic calculation with scenario-specific renewable energy growth)
    # Andorra context: mountain climate, hydroelectric potential, high renewable baseline
    # Base renewable energy share from 2024: 93.1% (from current.json data)
    base_renewable = 0.931  # 93.1% renewable energy share (2024)
    
    # Economic activity scaling: reference = 2024 actual GDPpc (42,852.96)
    gdp_scaling = GDPpc_next / 42852.96

    # Population and tourism energy demand scaling: reference = 2024 actuals
    pop_tour_scaling = (Pop_next + Tour_t1) / (87097.0 + 9646656.0)  # Combined scaling
    
    # Renewable energy investment factors by scenario
    investment_factor = p("Ren_investment_factor", 1.0)
    
    # Technology advancement factor (renewable energy becomes more cost-effective over time)
    tech_advancement = 1.0 + 0.05  # 5% improvement over 10 years
    
    # Calculate renewable energy share with realistic components
    # Higher economic activity and investment → higher renewable share
    renewable_growth = (gdp_scaling - 1.0) * 0.1 + (investment_factor - 1.0) * 0.15
    
    # Ensure renewable energy doesn't exceed 100% but can grow from high baseline
    Ren_next = clamp(base_renewable + renewable_growth * tech_advancement, 0.85, 0.98)

    # Air Quality Index (Andorra-specific calculation with realistic variations)
    # Andorra context: high altitude, 90% natural coverage, mountain environment
    # Use current AQI as base (from 2024 data or state)
    # AQI should be in 0-500 range (excellent: 0-50, good: 51-100)
    # Handle unrealistic values (like 6015.0) by dividing by 1000
    if AQI_t > 100:
        base_aqi = AQI_t / 1000.0  # Fix incorrectly stored values (6015.0 -> 6.015)
    elif AQI_t > 0 and AQI_t <= 500:
        base_aqi = AQI_t
    else:
        base_aqi = 6.015  # Default excellent mountain air quality for Andorra (2024 baseline)
    
    # Population density impact on air quality (small impact due to mountain environment)
    # Higher density = slightly worse air quality, but mountain winds help dispersion
    base_density = 87097.0 / 468.0  # people per km² (2024)
    current_density = Pop_next / 468.0  # people per km² (future)
    density_ratio = current_density / base_density
    
    # Density impact on AQI: very small impact due to mountain environment
    density_impact = (density_ratio - 1.0) * 0.3  # 0.3 AQI points per density doubling (very small)
    
    # CO2 per capita impact (emissions intensity) - minimal impact due to natural coverage
    co2_impact = (CO2pc_next - 5.396) * 0.05  # 0.05 AQI points per ton CO2pc change (minimal)
    
    # Natural coverage benefit (90% natural coverage provides clean air baseline)
    natural_benefit = (NatCov_next - 0.9307) * -1.0  # Small impact from natural coverage changes
    
    # Mountain altitude benefit (high altitude provides better air quality) - already in baseline
    altitude_benefit = 0.0  # Already factored into baseline value of 6.015
    
    # Renewables impact (clean energy reduces air pollution) - very small multiplier
    # Only count improvement beyond baseline (0.931), so high renewables don't over-correct
    ren_improvement = max(0, Ren_t - 0.931)  # Only positive changes
    ren_impact = ren_improvement * -0.5  # 0.5 AQI points improvement per 10% renewables increase beyond baseline
    
    # Tourism impact on air quality: reference = 2024 actual (9,646,656)
    AQI_chi = p("AQI_chi", 0.15)  # Tourism impact parameter
    tour_ratio = Tour_t1 / 9646656.0  # Normalize to 2024 actual tourism
    tour_impact = (tour_ratio - 1.0) * AQI_chi * 0.5  # Small impact from tourism growth
    
    # Calculate AQI with Andorra-specific bounds (excellent range with realistic variations)
    # Based on actual data: 2010-2024 range is 8.4-13.47 (all excellent mountain air quality)
    # Minimum 7.0 (excellent air), maximum 14.0 (still excellent) for mountain environment
    # Starting from 8.40 (2024), values should stay in excellent range with small variations
    AQI_next = clamp(base_aqi + density_impact + co2_impact + natural_benefit + altitude_benefit + ren_impact + tour_impact, 7.0, 14.0)


    # Water consumption (realistic calculation with population, economic activity, and tourism)
    # Andorra context: mountain climate, tourism industry, population water needs
    # Always use 2024 baseline (53655 L/day) as the base to avoid exponential compounding
    base_water_2024 = 53655.0  # 2024 baseline water consumption L/day
    
    # 2024 baseline values for scaling (all from verified Andorra statistics)
    base_pop_2024 = 87097.0
    base_gdp_2024 = 42852.96   # Actual 2024 GDPpc (Govern d'Andorra)
    base_tour_2024 = 9646656.0  # Actual 2024 tourist arrivals
    
    # Calculate years from 2024 for gradual scenario factor application
    # Use target_year from exog if available (set in simulate_path), otherwise use state Year + 1
    target_year = x("target_year", None)
    if target_year is None:
        # If not provided, infer from state Year (Year is updated after step_next)
        # For first iteration, Year is 2024, so we're calculating for 2025
        current_year = S.get("Year", 2024)
        # If Year is still 2024, we're calculating for 2025 (first future year)
        # Otherwise, we're calculating for current_year + 1
        years_from_2024 = max(1, (current_year + 1) - 2024) if current_year == 2024 else max(1, current_year - 2024)
    else:
        years_from_2024 = max(0, target_year - 2024)
    
    # Calculate scaling factors relative to 2024 baseline (not previous year)
    pop_change = (Pop_next - base_pop_2024) / base_pop_2024  # Population change ratio from 2024
    gdp_change = (GDPpc_next - base_gdp_2024) / base_gdp_2024  # GDP per capita change ratio from 2024
    tour_change = (Tour_t1 - base_tour_2024) / base_tour_2024  # Tourism change ratio from 2024
    
    # Water consumption components (weighted by impact on water demand)
    # These represent the impact on water demand relative to 2024 baseline
    pop_water_impact = pop_change * 0.4  # 40% population impact
    gdp_water_impact = gdp_change * 0.3  # 30% economic activity impact
    tour_water_impact = tour_change * 0.3  # 30% tourism impact
    
    # Total water demand change from 2024 baseline (cumulative, not per-year)
    water_change_factor = 1.0 + pop_water_impact + gdp_water_impact + tour_water_impact
    
    # Water efficiency improvement (cumulative: 1% per year from 2024)
    efficiency_improvement = years_from_2024 * 0.01  # 1% efficiency improvement per year cumulative
    efficiency_factor = 1.0 - efficiency_improvement  # Cumulative efficiency factor
    
    # Scenario-specific water consumption factors - apply gradually over 11 years (2025-2035)
    # This ensures 2025 values are close to 2024 baseline (within ~2-3% of baseline)
    base_scenario_factor = p("Water_scenario_factor", 1.0)
    # Interpolate scenario factor: 1.0 at 2024, base_scenario_factor at 2035
    # For 2025, use a much smaller weight to keep values very close to baseline
    if years_from_2024 <= 0:
        scenario_factor = 1.0  # 2024: no scenario effect
    elif years_from_2024 == 1:
        # 2025: apply only 10% of scenario effect to keep close to baseline
        gradual_weight = 0.1  # Much smaller for first year
        scenario_factor = 1.0 + (base_scenario_factor - 1.0) * gradual_weight
    else:
        # Years 2-11: apply gradually, with more weight in later years
        # Use a quadratic interpolation that accelerates in later years
        # For year 2: weight = 0.15, for year 11: weight = 1.0
        gradual_weight = min(0.1 + (years_from_2024 - 1) * 0.09, 1.0)  # 0.1 at year 1, ~1.0 at year 11
        scenario_factor = 1.0 + (base_scenario_factor - 1.0) * gradual_weight
    
    # Calculate water consumption: always from 2024 baseline, not previous year
    # This prevents exponential growth from compounding
    Water_next = base_water_2024 * water_change_factor * efficiency_factor * scenario_factor

    # Temperature (realistic calculation with climate change and urban heat island effects)
    # Andorra context: mountain climate, urban heat island effects from development
    # Base temperature from 2024: 7.46°C (from current.json data)
    base_temp = 7.46  # °C (Andorra's actual 2024 temperature)
    
    # Climate change progression (+0.15°C per decade)
    climate_change = 0.15  # °C increase over 10 years
    
    # Urban heat island effect based on development intensity
    # More buildings and population = higher local temperature
    base_density = 87097.0 / 468.0  # people per km² (2024)
    current_density = Pop_next / 468.0  # people per km² (future)
    density_ratio = current_density / base_density
    
    # Urban heat island effect: higher density = higher temperature
    uhi_effect = (density_ratio - 1.0) * 0.8  # 0.8°C per density doubling
    
    # Natural coverage cooling effect (more nature = cooler).
    # Reference = 2024 actual NatCov (0.9307). Prior code used 0.9359 (the 2010 value),
    # which introduced a spurious residual cooling offset at the 2024 baseline.
    natural_cooling = (NatCov_next - 0.9307) * -2.0  # -2°C per 10% natural coverage increase
    
    # CO2 per capita warming effect (more emissions = warmer)
    co2_warming = (CO2pc_next - 5.396) * 0.3  # 0.3°C per ton CO2pc increase
    
    # Scenario-specific adjustments
    scenario_factor = p("Temp_scenario_factor", 0.0)
    
    # Calculate temperature with realistic bounds for mountain climate
    Temp_next = clamp(base_temp + climate_change + uhi_effect + natural_cooling + co2_warming + scenario_factor, 6.0, 14.0)

    # ========== Infrastructure Calculations ==========
    # Get scenario name from exog or params (default to "CO" for Continuity if not specified)
    scenario_name = x("scenario_name", p("scenario_name", "CO"))
    
    # Map scenario names to infrastructure scenario codes
    scenario_map = {
        "Overgrowth": "OG",
        "Continuity": "CO",
        "Degrowth": "DG",
        "Density": "DN",
        "current": "CO",  # Current/Historical uses Continuity parameters
        "Historical": "CO"
    }
    infra_scenario = scenario_map.get(scenario_name, "CO")
    
    # Calculate infrastructure with current population
    # Use a custom config that uses Pop_next instead of fixed scenario populations
    infra_config = deepcopy(INFRASTRUCTURE_CONFIG)
    infra_config["populations"][infra_scenario] = Pop_next  # Use actual population
    
    # Calculate infrastructure
    try:
        infra_result = computeInfrastructureScenario(infra_scenario, config=infra_config)
        
        # Extract infrastructure values for state
        infrastructure = {
            "ElectricityPerCapita_kWh_year": infra_result["electricity"]["perCapita_kWh_year"],
            "ElectricityDemand_kWh_year": infra_result["electricity"]["demand_kWh_year"],
            "ElectricityCapacity_kW": infra_result["electricity"]["capacity_kW"],
            "ElectricityRenewable_kW": infra_result["electricity"]["renewableCapacity_kW"],
            "ElectricityFossil_kW": infra_result["electricity"]["fossilCapacity_kW"],
            "WaterPerCapita_L_day": infra_result["water"]["perCapita_L_day"],
            "WaterHousehold_m3_year": infra_result["water"]["householdDemand_m3_year"],
            "WaterTotal_m3_year": infra_result["water"]["totalDemand_m3_year"],
            "WaterSecurityIndex": infra_result["water"]["waterSecurityIndex"],
            "HospitalBaselineBeds": infra_result["hospitals"]["baselineBeds"],
            "HospitalRequiredBeds": infra_result["hospitals"]["requiredBeds"],
            "HospitalDeltaBeds": infra_result["hospitals"]["deltaBeds"],
            "SchoolStudents": infra_result["schools"]["students"],
            "SchoolClassrooms": infra_result["schools"]["classrooms"],
            "SchoolSchools": infra_result["schools"]["schools"],
            "RoadTotalLength_km": infra_result["roads"]["totalLength_km"],
            "RoadPerCapita_m": infra_result["roads"]["perCapita_m"]
        }
    except Exception as e:
        # If infrastructure calculation fails, use defaults
        print(f"Warning: Infrastructure calculation failed: {e}")
        infrastructure = {
            "ElectricityPerCapita_kWh_year": 3000.0,
            "ElectricityDemand_kWh_year": Pop_next * 3000.0,
            "ElectricityCapacity_kW": 0.0,
            "ElectricityRenewable_kW": 0.0,
            "ElectricityFossil_kW": 0.0,
            "WaterPerCapita_L_day": 150.0,
            "WaterHousehold_m3_year": 0.0,
            "WaterTotal_m3_year": 0.0,
            "WaterSecurityIndex": 0.0,
            "HospitalBaselineBeds": 0.0,
            "HospitalRequiredBeds": 0.0,
            "HospitalDeltaBeds": 0.0,
            "SchoolStudents": 0.0,
            "SchoolClassrooms": 0.0,
            "SchoolSchools": 0.0,
            "RoadTotalLength_km": 269.0,
            "RoadPerCapita_m": 0.0
        }

    out_state = {
        "Pop": Pop_next, "ForeignBorn": FB_next, "sForeignBorn": sFB_next,
        "Access": Access_next, "LE": LE_next, "WLB": WLB_next,
        "GDPpc": GDPpc_next, "Income": Income_next, "Salary": Salary_next,  # Income = Median household income (annual)
        "BusinessFormation": BusinessFormation_next,
        "B": B_next, "HPrice": HPrice_next, "HPrice_prev": HPrice_t, "Afford": Afford_next,
        "GDPpc_prev": GDPpc_t, "GDPpc_prev2": GDPpc_prev,  # lags for GDP→population model
        "NatCov": NatCov_next, "CO2pc": CO2pc_next, "CO2_total": CO2_total_next,
        "Ren": Ren_next, "AQI": AQI_next, "Water": Water_next,
        "Temp": Temp_next, "Tour": Tour_t1,
        "GDP": GDPpc_next * Pop_next,
        "Marriages": Marriages_next, "Divorces": Divorces_next, "FamilyStability": FamilyStability_next,
        "Emp": Emp_next,  # Employment rate
        **({"Divorces_annual_avg": S["Divorces_annual_avg"]} if "Divorces_annual_avg" in S else {}),
        **infrastructure  # Add all infrastructure fields
    }
    return {"state": out_state, "params": P, "exog": X}

# ========== dynamic parameter calculation ==========
def calculate_dynamic_parameters(scenario_name, current_state, existing_params=None):
    """Calculate scenario-specific parameters based on population, tourism, and destination assumptions.

    existing_params: optional dict from which ``_calib_*`` private keys are inherited so that
                     calibrated base values (from calibrate_historical_parameters) supersede
                     the hardcoded priors while scenario-specific adjustments remain active.
    """
    
    # Load scenario assumptions
    here = Path(__file__).resolve().parent
    scenario_path = here.parent.parent / "conf" / "scenarios" / f"{scenario_name.lower()}.json"
    
    if scenario_path.exists():
        with scenario_path.open("r") as f:
            scenario_config = json.load(f)
        assumptions = scenario_config.get("assumptions", {})
    else:
        # Fallback assumptions if config file doesn't exist
        if scenario_name == "Overgrowth":
            assumptions = {"gdp_growth_rate": 0.060, "tourism_growth_rate": 0.025, "co2_intensity_change": 0.005}
        elif scenario_name == "Degrowth":
            assumptions = {"gdp_growth_rate": -0.015, "tourism_growth_rate": -0.010, "co2_intensity_change": -0.010}
        elif scenario_name == "Density":
            assumptions = {"gdp_growth_rate": 0.030, "tourism_growth_rate": 0.020, "co2_intensity_change": -0.005, "pop_elasticity_factor": 0.55}
        else:  # Continuity
            assumptions = {"gdp_growth_rate": 0.025, "tourism_growth_rate": 0.008, "co2_intensity_change": -0.005}

    gdp_growth_rate   = assumptions.get("gdp_growth_rate",  0.025)
    tour_growth_rate  = assumptions.get("tourism_growth_rate", 0.01)
    co2_intensity_change = assumptions.get("co2_intensity_change", -0.005)
    pop_elasticity_factor = assumptions.get("pop_elasticity_factor", 1.0)
    # Derive an approximate annual population growth rate for parameters that
    # still need a pop_growth_rate proxy (e.g. environmental/health params).
    # Use the distributed-lag formula: ~0.40*gGDP (dominant term, lag-1 only).
    pop_growth_rate = 0.40 * gdp_growth_rate * pop_elasticity_factor
    
    # Current state values
    Pop0 = current_state.get("Pop", 87097)
    Tour0 = current_state.get("Tour", 8000000)
    GDPpc0 = current_state.get("GDPpc", 45000)
    
    # Calculate dynamic parameters based on scenario characteristics
    params = {}
    # Seed any private calibration keys from the upstream params dict so that
    # the _base_* lookups below find the calibrated values instead of hardcoded priors.
    if existing_params:
        for k, v in existing_params.items():
            if k.startswith("_calib_"):
                params[k] = v

    # Population-related parameters — GDP-driven model
    params["gnat"] = -0.001  # Andorra: births < deaths, fixed natural rate
    params["beta_gdp_lag1"] = 0.40  # distributed-lag beta (year t-1)
    params["beta_gdp_lag2"] = 0.10  # distributed-lag beta (year t-2)
    params["beta_afford"]   = 0.10  # housing-affordability suppressor
    params["pop_elasticity_factor"] = pop_elasticity_factor
    # Keep legacy params for modules that still read them
    params["beta1"] = 0.15 + abs(pop_growth_rate) * 5
    params["beta2"] = 0.25 + abs(pop_growth_rate) * 2
    params["beta3"] = 0.08 + abs(pop_growth_rate) * 3
    
    # Tourism-related parameters
    # Key must match step_next lookup: p("GDPpc_gamma2", 0.1)
    # Prior base = 0.05; overridden by calibrated value when available.
    _base_gamma2 = params.get("_calib_GDPpc_gamma2", 0.05)
    params["GDPpc_gamma2"] = _base_gamma2 + tour_growth_rate * 2  # GDP sensitivity to tourism
    params["theta_tour_load"] = 0.2 + tour_growth_rate * 5  # Health system load from tourism
    params["AQI_chi"] = 0.15 + tour_growth_rate * 3  # Tourism impact on air quality
    
    # Economic parameters based on growth assumptions
    growth_factor = (pop_growth_rate + tour_growth_rate) / 2

    # gTFP (Total Factor Productivity): prior base = 0.016; overridden by calibrated value
    # when calibrate_historical_parameters() has been run (passed via calib_params).
    # Scenario adjustment is additive on top of the base so all scenarios inherit the
    # historically-fitted correction while keeping their relative ordering.
    _base_gTFP = params.get("_calib_gTFP", 0.016)
    params["gTFP"] = _base_gTFP + growth_factor * 0.1

    # Income_a1: Income = a1 × GDPpc. Prior = 1.2958; overridden by calibrated value.
    _base_Income_a1 = params.get("_calib_Income_a1", 1.2958)
    params["Income_a1"] = _base_Income_a1 + growth_factor * 0.1

    # Salary_ratio: monthly_salary / (annual_income / 12).
    # 2024: Salary = 2,571; Income_annual = 55,534 → monthly_income = 4,627.8
    # ratio = 2,571 / 4,627.8 = 0.5556 ≈ 0.556 ✓ (unchanged)
    params["Salary_ratio"] = 0.556 + growth_factor * 0.05
    
    # Business formation parameters (realistic scaling)
    params["BF_bf1"] = 0.4 + abs(pop_growth_rate) * 2  # Population scaling factor (0.4 to 0.5 range)
    params["BF_bf2"] = 0.2 + abs(growth_factor) * 0.5  # Income growth sensitivity
    params["BF_bf3"] = 0.15 + abs(tour_growth_rate) * 0.5  # Tourism growth sensitivity
    
    # Housing and affordability
    params["H_h1"] = 0.3 + growth_factor * 0.1  # Income sensitivity to housing prices (realistic)
    params["H_h2"] = 1.2 + abs(pop_growth_rate) * 3  # Population density sensitivity
    params["Afford_k"] = 1.0 - growth_factor * 0.5  # Affordability adjustment
    
    # Building permit parameters (for formula-based B calculation)
    # Formula: Permits = phi0 + phi1 * growth(Pop) + phi2 * growth(HPrice) - phi3 * LandProtect
    # B_next = B_t + Permits - delta_demo * B_t
    # Calibrated: For 1% pop growth, want ~1% B growth to maintain density
    # With delta_demo = 0.01, need Permits ≈ B_t * 0.02 for 1% net growth
    # So phi1 * 0.01 ≈ B_t * 0.02, therefore phi1 ≈ B_t * 2.0
    B0 = current_state.get("B", 10645)
    Pop0 = current_state.get("Pop", 87097)
    ppb0 = Pop0 / B0 if B0 > 0 else 8.18  # persons per building (baseline ~8.18)
    
    if scenario_name == "overgrowth":
        # High responsiveness to population growth, calibrated to roughly match Pop growth
        # Target: B grows ~1.0x relative to Pop (maintain density)
        # Note: phi1 is constant, so as B grows, same permits = smaller % growth (compensate with higher phi1)
        params["Perm_phi0"] = 80.0  # Base annual permits
        params["Perm_phi1"] = B0 * 2.1  # Calibrated to match ~10% annual pop growth
        params["Perm_phi2"] = B0 * 0.3  # Moderate response to housing price growth
        params["Perm_phi3"] = 15.0  # Moderate land protection impact
    elif scenario_name == "degrowth":
        # Low responsiveness, minimal base permits, strong land protection
        # Target: B decreases but slower than Pop (some buildings remain)
        params["Perm_phi0"] = 3.0  # Very low base permits
        params["Perm_phi1"] = B0 * 0.15  # Weak response to population growth
        params["Perm_phi2"] = B0 * 0.03  # Weak response to housing price growth
        params["Perm_phi3"] = 100.0  # Strong land protection impact (discourages building)
    elif scenario_name == "density":
        # No building expansion: minimal permits, strong land protection (Barcelona-like density, same footprint)
        params["Perm_phi0"] = 2.0  # Minimal new construction
        params["Perm_phi1"] = B0 * 0.05  # Almost no response to population growth (no sprawl)
        params["Perm_phi2"] = B0 * 0.02  # Weak response to housing price (avoid new build)
        params["Perm_phi3"] = 150.0  # Very strong land protection (no expansion)
    else:  # continuity
        # Moderate responsiveness, calibrated to roughly match Pop growth over time
        # Note: Since phi1 is constant but B grows, need higher phi1 to maintain growth rate
        params["Perm_phi0"] = 40.0  # Moderate base permits
        params["Perm_phi1"] = B0 * 1.6  # Higher to compensate for growth rate slowing as B increases
        params["Perm_phi2"] = B0 * 0.2  # Moderate response to housing price growth
        params["Perm_phi3"] = 30.0  # Moderate land protection impact
    
    # Environmental parameters
    params["CO2_eta"] = 0.4 - co2_intensity_change * 10  # Renewables impact on CO2
    params["Ren_rho1"] = 0.1 + abs(co2_intensity_change) * 5  # Renewables capacity addition
    params["Nat_sigma1"] = 0.3 + abs(pop_growth_rate) * 2  # Urbanization impact on nature
    
    # Health and quality of life
    params["LE_b1"] = 2.5 - abs(growth_factor) * 0.5  # Health access impact
    params["WLB_c1"] = 0.25 - growth_factor * 0.3  # Productivity impact on work-life balance
    params["WLB_c2"] = 0.08 + tour_growth_rate * 2  # Tourism job pressure
    
    # Employment parameters
    params["Emp_kappa1"] = 0.35 + growth_factor * 1.5  # GDP growth sensitivity
    params["Emp_kappa2"] = 0.12 + abs(pop_growth_rate) * 2  # Migration impact
    
    # Temperature scenario factors
    if scenario_name == "overgrowth":
        params["Temp_scenario_factor"] = 0.3  # Additional warming from intense development
    elif scenario_name == "degrowth":
        params["Temp_scenario_factor"] = -0.2  # Cooling from reduced development
    elif scenario_name == "density":
        params["Temp_scenario_factor"] = 0.1  # Slight UHI from higher density, no new land
    else:  # continuity
        params["Temp_scenario_factor"] = 0.0  # Baseline scenario

    # Water consumption scenario factors
    if scenario_name == "overgrowth":
        params["Water_scenario_factor"] = 1.2  # Higher water consumption from intense development and tourism
    elif scenario_name == "degrowth":
        params["Water_scenario_factor"] = 0.8  # Lower water consumption from reduced activity
    elif scenario_name == "density":
        params["Water_scenario_factor"] = 1.1  # Slightly higher use with more people, same footprint
    else:  # continuity
        params["Water_scenario_factor"] = 1.0  # Baseline scenario

    # Renewable energy investment scenario factors
    if scenario_name == "overgrowth":
        params["Ren_investment_factor"] = 1.3  # Higher renewable investment from economic growth and energy needs
    elif scenario_name == "degrowth":
        params["Ren_investment_factor"] = 0.9  # Lower renewable investment from reduced economic activity
    elif scenario_name == "density":
        params["Ren_investment_factor"] = 1.15  # Higher investment (compact, efficient)
    else:  # continuity
        params["Ren_investment_factor"] = 1.1  # Moderate renewable investment growth

    return params

# ========== scenario builders (targets only) ==========
def scenario_targets(current_state, scenario_name):
    """Return (GDPpc_T, Tour_T, B_target_fn, alpha_fb).

    GDPpc_T is the exogenous GDP-per-capita target at year+11.
    Population is now endogenous (driven by GDP via distributed-lag model).
    Tour_T is kept proportional to the *approximate* end-state population,
    which is derived here for reference only (not used for forcing).
    """
    Pop0  = current_state["Pop"];  B0    = current_state["B"]
    Tour0 = current_state["Tour"]; GDPpc0 = current_state.get("GDPpc", 45_000)
    ppb0  = (Pop0 / B0) if B0 > 0 else 0.0
    tourists_per_person_2024 = Tour0 / max(Pop0, 1e-9)

    # Load gdp_growth_rate from the scenario config JSON
    here = Path(__file__).resolve().parent
    scenario_path = here.parent.parent / "conf" / "scenarios" / f"{scenario_name.lower()}.json"
    gdp_growth_rate = 0.025  # fallback: continuity
    pop_elasticity_factor = 1.0
    if scenario_path.exists():
        with scenario_path.open("r") as f:
            cfg = json.load(f)
        gdp_growth_rate       = cfg.get("assumptions", {}).get("gdp_growth_rate", gdp_growth_rate)
        pop_elasticity_factor = cfg.get("assumptions", {}).get("pop_elasticity_factor", 1.0)

    # Exogenous GDP target: compound growth over 11 years
    GDPpc_T = GDPpc0 * (1.0 + gdp_growth_rate) ** 25

    # Approximate final population from distributed-lag elasticity (informational only):
    #   gPop ≈ gnat + (beta_lag1+beta_lag2) * gGDP * elas_factor  each year
    beta_sum = (0.40 + 0.10) * pop_elasticity_factor
    gnat     = -0.001
    gPop_approx = gnat + beta_sum * gdp_growth_rate
    Pop_T_approx = int(round(Pop0 * (1.0 + gPop_approx) ** 25))

    # Tourism proportional to approximate end-state population
    Tour_T = int(round(Pop_T_approx * tourists_per_person_2024))

    # Building stock target functions (unchanged by GDP model inversion)
    if scenario_name == "Overgrowth":
        def B_target(Pop_t): return int(round(Pop_t / max(ppb0, 1e-9)))
        alpha_fb = 1.0
    elif scenario_name == "Degrowth":
        def B_target(_Pop_t): return B0
        alpha_fb = 1.0
    elif scenario_name == "Density":
        def B_target(_Pop_t): return B0
        alpha_fb = 1.0
    else:  # Continuity
        def B_target(Pop_t): return int(round(Pop_t / max(ppb0, 1e-9)))
        alpha_fb = 1.0

    return GDPpc_T, Tour_T, B_target, alpha_fb

# ========== simulate multi-year path ==========
def simulate_path(current, scenario_name, years=10, start_year=None, param_overrides=None):
    """
    Args:
        param_overrides: optional dict of parameter values applied AFTER dynamic params,
                         so they take precedence. Used by Monte Carlo to perturb gTFP etc.
    """
    base = deepcopy(current)
    base.setdefault("state", {})
    base.setdefault("params", {})
    base.setdefault("exog", {})

    # Preserve any calibrated base values that were pre-set in current["params"]
    # by hoisting them into the params dict under private "_calib_*" keys.
    # calculate_dynamic_parameters reads these to replace its hardcoded priors,
    # so the calibrated fit is respected while scenario-specific adjustments remain.
    _calib_keys = {
        "gTFP":         "_calib_gTFP",
        "GDPpc_gamma2": "_calib_GDPpc_gamma2",
        "Income_a1":    "_calib_Income_a1",
    }
    for pub, priv in _calib_keys.items():
        if pub in base["params"]:
            base["params"][priv] = base["params"][pub]

    dynamic_params = calculate_dynamic_parameters(scenario_name, base["state"],
                                                   existing_params=base["params"])
    base["params"].update(dynamic_params)
    if param_overrides:
        base["params"].update(param_overrides)

    year0 = start_year if start_year is not None else int(base["state"].get("Year", 2025))

    S0 = deepcopy(base["state"])
    Pop0, Tour0, B0 = S0.get("Pop", 0), S0.get("Tour", 0), S0.get("B", 0)
    GDPpc0 = S0.get("GDPpc", 45_000)

    GDPpc_T, Tour_T, B_target_fn, alpha_fb = scenario_targets(S0, scenario_name)

    # Seed 1-year and 2-year GDPpc lags in the initial state if not already present.
    # Andorra 2024: +3.8%; 2023: +9.6% (IMF). Approximate 2023 and 2022 values.
    if "GDPpc_prev" not in base["state"]:
        base["state"]["GDPpc_prev"]  = GDPpc0 / 1.038
    if "GDPpc_prev2" not in base["state"]:
        base["state"]["GDPpc_prev2"] = GDPpc0 / (1.038 * 1.096)

    tourists_per_person_2024 = Tour0 / max(Pop0, 1e-9)

    timeline = []
    curr = deepcopy(base)

    for t in range(1, years + 1):
        # Interpolate the exogenous GDP-per-capita path
        GDPpc_tgt = interp_linear(GDPpc0, GDPpc_T, t, years)

        # Tourism proportional to *current* population (lagged one step to avoid bootstrap)
        Pop_curr = curr["state"].get("Pop", Pop0)
        Tour_tgt = tourists_per_person_2024 * Pop_curr
        B_tgt    = B_target_fn(Pop_curr)

        force_build = (scenario_name == "Density")
        ex = deepcopy(curr.get("exog", {}))
        ex.update({
            "GDPpc_target":  GDPpc_tgt,
            "force_gdp":     True,
            "force_pop":     False,   # population is endogenous
            "Tour_target":   Tour_tgt,
            "force_tour":    True,
            "B_target":      B_tgt,
            "force_build":   force_build,
            "alpha_fb":      alpha_fb,
            "scenario_name": scenario_name,
            "target_year":   year0 + t,
        })
        curr["exog"] = ex

        res = step_next(curr)
        res["state"]["Year"] = year0 + t

        timeline.append(deepcopy(res["state"]))

        curr["state"]  = deepcopy(res["state"])
        curr["params"] = curr.get("params", {})
        curr["exog"]   = curr.get("exog", {})

    return timeline, timeline[-1]

# ========== historical calibration (P1) ==========
def extract_state_for_year(data_list, year):
    """Extract model state dict for a specific historical year from Current.json list format.
    Uses the same Unicode-safe field matching as transform_data_from_list_format."""
    data_rows = [row for row in data_list[1:]
                 if row.get("Unnamed: 0") and
                 row["Unnamed: 0"] not in ["SOCIAL", "ECONOMICAL", "ECONOMIC",
                                           "ENVIROMENTAL", "ENVIRONMENTAL",
                                           "INFRASTRUCTURE", "BUILDINGS", "HEALTH"]]
    year_str = str(year)
    state = {}
    for row in data_rows:
        metric_name = row["Unnamed: 0"]
        m = _norm(metric_name)
        val = row.get(year_str)
        if val is None:
            continue
        if "population growth" in m:
            state["Pop"] = val
        elif "life expect" in m:
            state["LE"] = val
        elif "gdp per capita" in m:
            state["GDPpc"] = val
        elif "employment rate" in m:
            state["Emp"] = val
        elif "median" in m and "house" in m and "price" in m and "income" not in m:
            state["HPrice"] = val
        elif "tourism" in m or "tourist" in m:
            state["Tour"] = val
        elif "number of buildings" in m:
            state["B"] = val
        elif "foreign" in m and "born" in m and "%" not in m:
            state["ForeignBorn"] = val
        elif "work" in m and "life" in m and "balance" in m:
            state["WLB"] = val
        elif "acces" in m and "health" in m:
            state["Access"] = val
        elif "median" in m and "household" in m and "income" in m:
            state["Income"] = val * 12  # monthly → annual
        elif "average monthly salary" in m:
            state["Salary"] = val
        elif "affordability" in m or ("housing" in m and "%" in m):
            state["Afford"] = val * 100
        elif "natural coverage" in m:
            state["NatCov"] = val
        elif "co2 emissions per capita" in m:
            state["CO2pc"] = val
        elif "renewable energy share" in m or "renewables" in m:
            state["Ren"] = val / 100.0 if val > 1 else val
        elif "air quality" in m:
            state["AQI"] = val / 1000.0 if val > 100 else val
        elif "water consumption" in m:
            state["Water"] = val
        elif "temperature" in m or "avg temp" in m:
            state["Temp"] = val
        elif "marriages" in m:
            state["Marriages"] = val
        elif "divorces" in m:
            year_vals = [row.get(str(y)) for y in range(2010, 2025)
                         if row.get(str(y)) is not None]
            if year_vals:
                avg = sum(year_vals) / len(year_vals)
                state["Divorces_annual_avg"] = avg
                state["Divorces"] = round(avg)
            else:
                state["Divorces"] = val
    state["Year"] = year

    # Derive HPrice from Afford × monthly Income so the historical calibration
    # uses consistent values.  The raw HPrice column in Current.json has a scale
    # break between 2013 and 2014 (values jump from ~570 to ~1500); computing
    # from Afford and Income gives a smooth, internally consistent series.
    if "Afford" in state and "Income" in state:
        state["HPrice"] = (state["Afford"] / 100.0) * (state["Income"] / 12.0)

    return state


def calibrate_historical_parameters(data_list):
    """
    Fit three free parameters to reproduce the 2010–2024 historical trajectory.

    Method: scipy.optimize.minimize (Nelder-Mead) minimising weighted RMSE between
    modelled and observed annual values of GDPpc, Emp, and CO2pc over 2011–2024
    (14 one-year steps stepping forward from the 2010 baseline).

    Free parameters
    ---------------
    gTFP       – total factor productivity growth rate   (prior ≈ 0.016)
    GDPpc_gamma2 – tourism elasticity of GDPpc           (prior ≈ 0.094)
    Income_a1  – median-household-income / GDPpc ratio   (prior ≈ 1.2958)

    Method notes
    ------------
    Population and tourism are forced to the observed historical series so the
    optimiser only needs to explain the endogenous economic variables.  CO2pc is
    included to prevent the optimiser from finding implausible high-growth paths
    that fit GDPpc at the cost of unrealistic emissions.

    Returns
    -------
    dict with calibrated values, RMSE, and a ``calibrated`` flag.
    """
    try:
        from scipy.optimize import minimize as sp_minimize
    except ImportError:
        print("Warning: scipy not available — skipping historical calibration.")
        return {"gTFP": 0.016, "GDPpc_gamma2": 0.094, "Income_a1": 1.2958,
                "rmse": None, "success": False, "calibrated": False}

    # ---------- observed series 2011–2024 ----------
    years = list(range(2011, 2025))
    obs = {yr: extract_state_for_year(data_list, yr) for yr in years}

    # ---------- 2010 initial state (fill missing with calibrated 2024 defaults) ----------
    s0 = extract_state_for_year(data_list, 2010)
    _defaults = {
        "Pop": 87097, "GDPpc": 42852.96, "Emp": 0.9852, "HPrice": 1332.734,
        "Tour": 9646656, "B": 10645, "ForeignBorn": 30000, "LE": 84.5,
        "WLB": 0.6, "Access": 0.922, "Income": 55533.6, "Salary": 2571,
        "Afford": 28.79843554, "NatCov": 0.9307, "CO2pc": 5.396,
        "CO2_total": 470000, "Ren": 0.931, "AQI": 8.40, "Water": 53655,
        "Temp": 7.46, "Beds": 2000, "PriceIdx": 1.0, "GlobalTravel": 1.0,
        "LaborShare": 0.55, "Rate": 0.03, "TourHomeDemand": 0.0,
        "GDP": 42852.96 * 87097, "BusinessFormation": 1450,
        "Marriages": 438, "Divorces": 98, "FamilyStability": 0.225,
    }
    for k, v in _defaults.items():
        s0.setdefault(k, v)
    s0["Year"] = 2010

    # ---------- loss function ----------
    # Weights: Emp scaled up (small fractional range); CO2pc keeps model honest
    _weights = {"GDPpc": 1.0, "Emp": 100.0, "CO2pc": 5.0}

    def _rmse(params):
        gTFP, gamma2, Income_a1 = params
        # Soft bounds via penalty (avoids discontinuity during Nelder-Mead)
        if not (0.0 < gTFP < 0.06 and 0.0 < gamma2 < 0.5 and 0.8 < Income_a1 < 2.0):
            return 1e9
        curr_state = deepcopy(s0)
        total_sq, n = 0.0, 0
        for yr in years:
            yr_obs = obs.get(yr, {})
            Pop_obs  = yr_obs.get("Pop",  curr_state.get("Pop",  87097))
            Tour_obs = yr_obs.get("Tour", curr_state.get("Tour", 9646656))
            B_obs    = yr_obs.get("B",    curr_state.get("B",    10645))
            bundle = {
                "state": deepcopy(curr_state),
                "params": {
                    "gTFP": gTFP,
                    "GDPpc_gamma2": gamma2,
                    "Income_a1": Income_a1,
                    "Income_a0": 0.0,
                    "Income_a2": 0.0,
                },
                "exog": {
                    "Pop_target":  Pop_obs,
                    "Tour_target": Tour_obs,
                    "B_target":    B_obs,
                    "force_pop": True, "force_tour": True, "force_build": True,
                    "scenario_name": "Continuity",
                    "target_year": yr,
                    "gTFP": gTFP,
                },
            }
            try:
                ns = step_next(bundle)["state"]
            except Exception:
                return 1e9
            for var, w in _weights.items():
                mod = ns.get(var)
                hist = yr_obs.get(var)
                if mod is not None and hist is not None and hist != 0:
                    total_sq += w * ((mod - hist) / hist) ** 2
                    n += 1
            curr_state = ns
            curr_state["Year"] = yr
        return total_sq / max(n, 1)

    x0 = [0.016, 0.094, 1.2958]
    result = sp_minimize(_rmse, x0, method="Nelder-Mead",
                         options={"xatol": 1e-6, "fatol": 1e-8,
                                  "maxiter": 8000, "disp": False})
    gTFP_opt, gamma2_opt, Income_a1_opt = result.x
    return {
        "gTFP":         float(gTFP_opt),
        "GDPpc_gamma2": float(gamma2_opt),
        "Income_a1":    float(Income_a1_opt),
        "rmse":         float(result.fun),
        "success":      bool(result.success),
        "calibrated":   True,
    }


# ========== Monte Carlo uncertainty (P2) ==========
def monte_carlo_scenario(current, scenario_name, n_samples=500, seed=42):
    """
    Run Monte Carlo uncertainty analysis for a scenario.

    Three parameters are perturbed independently with truncated normal noise:
      gTFP        ±20%  – total factor productivity (dominant GDP driver)
      Income_a1   ±5%   – income/GDPpc ratio (tightly constrained by data)
      GDPpc_gamma2 ±25% – tourism elasticity of GDPpc (wider uncertainty)

    Returns a dict with p10/p50/p90 time series for key output variables,
    suitable for writing to ``{Scenario}_mc_summary.json``.
    """
    rng = random.Random(seed)

    key_vars = ["GDPpc", "Pop", "Emp", "WLB", "NatCov", "CO2pc", "Ren",
                "AQI", "LE", "Afford", "HPrice", "FamilyStability", "Water", "Temp"]

    # Baseline run to discover year sequence
    base_ts, _ = simulate_path(current, scenario_name, years=25,
                               start_year=current.get("state", {}).get("Year", 2024))
    years_seq = [st["Year"] for st in base_ts]
    n_years = len(years_seq)

    # Storage: samples[var][year_idx] = list of scalar values
    samples = {v: [[] for _ in range(n_years)] for v in key_vars}

    # Base dynamic params (scenario-specific centre values, using calibrated priors if available)
    base_dp = calculate_dynamic_parameters(scenario_name, current["state"],
                                           existing_params=current.get("params", {}))

    for _ in range(n_samples):
        # Sample multipliers: normal(1, σ) truncated to [1-3σ, 1+3σ]
        def _sample(sigma):
            lo, hi = max(0.1, 1.0 - 3 * sigma), 1.0 + 3 * sigma
            return max(lo, min(hi, 1.0 + rng.gauss(0.0, sigma)))

        overrides = {
            "gTFP":         base_dp.get("gTFP",         0.016) * _sample(0.20),
            "Income_a1":    base_dp.get("Income_a1",    1.2958) * _sample(0.05),
            "GDPpc_gamma2": base_dp.get("GDPpc_gamma2", 0.094)  * _sample(0.25),
        }
        try:
            ts, _ = simulate_path(current, scenario_name, years=25,
                                  start_year=current.get("state", {}).get("Year", 2024),
                                  param_overrides=overrides)
            for t_idx, state in enumerate(ts):
                for v in key_vars:
                    val = state.get(v)
                    if val is not None:
                        samples[v][t_idx].append(float(val))
        except Exception:
            pass  # discard failed runs; silently skipped

    def _pct(lst, p):
        """Compute p-th percentile of a list using linear interpolation."""
        if not lst:
            return None
        s = sorted(lst)
        idx = (len(s) - 1) * p / 100.0
        lo = int(idx)
        hi = min(lo + 1, len(s) - 1)
        return s[lo] + (s[hi] - s[lo]) * (idx - lo)

    summary = {
        "scenario":  scenario_name,
        "n_samples": n_samples,
        "years":     years_seq,
        "variables": {},
    }
    for v in key_vars:
        summary["variables"][v] = {
            "p10": [_pct(samples[v][i], 10) for i in range(n_years)],
            "p50": [_pct(samples[v][i], 50) for i in range(n_years)],
            "p90": [_pct(samples[v][i], 90) for i in range(n_years)],
        }
    return summary


# ========== data transformation ==========
def _norm(s):
    """Normalize metric name for robust matching against Unicode variants in Current.json.

    Current.json field names use several non-standard Unicode characters:
      U+202F narrow no-break space  (e.g. "GDP\u202fper\u202fCapita")
      U+00A0 non-breaking space     (e.g. "Median\u00a0House\u00a0Price")
      U+2011 non-breaking hyphen    (e.g. "Work\u2011Life Balance")
      U+2082 subscript '2'          (e.g. "CO\u2082 Emissions")
    All are mapped to their ASCII equivalents and the result is lower-cased so
    comparisons are both Unicode-safe and case-insensitive.
    """
    return (s.replace('\u202f', ' ').replace('\u00a0', ' ').replace('\u2009', ' ')
             .replace('\u2011', '-').replace('\u2010', '-')
             .replace('\u2082', '2').replace('\u2060', '')
             .strip().lower())


def transform_data_from_list_format(data_list):
    """Transform list-based JSON data to the expected dictionary format."""
    # Skip the header row (index 0) and section-header rows
    data_rows = [row for row in data_list[1:]
                 if row.get("Unnamed: 0") and
                 row["Unnamed: 0"] not in ["SOCIAL", "ECONOMICAL", "ECONOMIC",
                                           "ENVIROMENTAL", "ENVIRONMENTAL",
                                           "INFRASTRUCTURE", "BUILDINGS", "HEALTH"]]

    # Extract the latest year's data (2024)
    state = {}
    for row in data_rows:
        metric_name = row["Unnamed: 0"]
        m = _norm(metric_name)          # Unicode-normalised, lower-cased name
        value_2024 = row.get("2024")
        if value_2024 is not None:
            if "population growth" in m:
                state["Pop"] = value_2024
            elif "life expect" in m:                       # "Life expectency" or "Life expectancy"
                state["LE"] = value_2024
            elif "gdp per capita" in m or "gdp\xa0per\xa0capita" in m:
                state["GDPpc"] = value_2024
            elif "employment rate" in m:                   # case-insensitive now
                state["Emp"] = value_2024
            elif "median" in m and "house" in m and "price" in m and "income" not in m:
                # Median House Price (€/month)
                state["HPrice"] = value_2024
            elif "tourism" in m or "tourist" in m:
                state["Tour"] = value_2024
            elif "number of buildings" in m:
                state["B"] = value_2024
            elif "foreign" in m and "born" in m and "%" not in m:
                # "Foreign-born" count (not the %-share row)
                state["ForeignBorn"] = value_2024
            elif "work" in m and "life" in m and "balance" in m:
                state["WLB"] = value_2024
            elif "acces" in m and "health" in m:           # "Acces to health" (typo in data)
                state["Access"] = value_2024
            elif "median" in m and "household" in m and "income" in m:
                # Current.json stores monthly household income; convert to annual
                state["Income"] = value_2024 * 12
            elif "average monthly salary" in m:
                state["Salary"] = value_2024
            elif "affordability" in m or ("housing" in m and "%" in m):
                # Current.json stores as decimal fraction (0.288); convert to %
                state["Afford"] = value_2024 * 100
            elif "natural coverage" in m:
                state["NatCov"] = value_2024
            elif "co2 emissions per capita" in m or "co2\xa0emissions" in m and "per" in m:
                # Per-capita CO2 in tonnes/person (NOT total in KT despite misleading prior comment)
                state["CO2pc"] = value_2024
                state["CO2_total"] = value_2024 * 87097   # approximate 2024 total
            elif "total co2" in m:
                state["CO2_total"] = value_2024           # already in tonnes
            elif "renewable energy share" in m or "renewables" in m:
                # Current.json stores as percent (93.1); convert to fraction
                state["Ren"] = value_2024 / 100.0 if value_2024 > 1 else value_2024
            elif "air quality" in m:
                # Values stored ×1000 (e.g. 8400 means 8.4 μg/m³ PM2.5)
                state["AQI"] = value_2024 / 1000.0 if value_2024 > 100 else value_2024
            elif "water consumption" in m:
                state["Water"] = value_2024
            elif "temperature" in m or "avg temp" in m:
                state["Temp"] = value_2024
            elif "business formation" in m:
                state["BusinessFormation"] = value_2024
            elif "marriages" in m:
                state["Marriages"] = value_2024
            elif "divorces" in m:
                # 2024 raw value (13) is an extreme outlier; use 2010–2024 mean as the
                # operative rate so the model doesn't inherit an anomalous base.
                year_vals = [row.get(str(y)) for y in range(2010, 2025)
                             if row.get(str(y)) is not None]
                if year_vals:
                    avg = sum(year_vals) / len(year_vals)
                    state["Divorces_annual_avg"] = avg
                    state["Divorces"] = round(avg)
                else:
                    state["Divorces"] = value_2024
            elif "family stability" in m:
                state["FamilyStability"] = value_2024
            elif "school students" in m:
                state["SchoolStudents"] = value_2024
            elif "school classrooms" in m:
                state["SchoolClassrooms"] = value_2024
            elif "school schools" in m:
                state["SchoolSchools"] = value_2024
    
    # Set Year to 2024
    state["Year"] = 2024

    # Derive HPrice from Afford × monthly Income rather than the raw data value.
    # The raw "Median House Price" column in Current.json is inconsistent: 2010–2013
    # values are ~560–580 (wrong scale) while 2014–2024 values are ~1500–1850 (inflated
    # vs what affordability × income implies).  The formula below is the only path that
    # is internally consistent across ALL years and matches the 2024 model default of
    # 1332.734 (= 0.28798 × 4627.8).
    if "Afford" in state and "Income" in state:
        state["HPrice"] = (state["Afford"] / 100.0) * (state["Income"] / 12.0)

    # Set default values for missing metrics
    defaults = {
        "Pop": 87097, "GDPpc": 42852.96, "Emp": 0.9852, "HPrice": 1332.734, "Tour": 9646656,  # HPrice = monthly €/month (dashboard unit)
        "B": 10645, "ForeignBorn": 30000, "LE": 84.5, "WLB": 0.6, "Access": 0.922,
        "Income": 55533.6, "Salary": 2571, "Afford": 28.79843554, "NatCov": 0.9307, "CO2pc": 5.396, "CO2_total": 470000,  # Income = Median household income (annual), Salary = Average monthly salary (2,571 in 2024), NatCov = 0.9307 (2024 actual; prior 0.9359 was 2010 value), CO2pc = 5.396 t/cap, CO2_total = 470KT
        "Ren": 0.931, "AQI": 8.40, "Water": 53655, "Temp": 7.46,  # AQI = 8.40 (actual 2024 value, excellent mountain air quality)
        "Beds": 2000, "PriceIdx": 1.0, "GlobalTravel": 1.0, "LaborShare": 0.55,
        "Rate": 0.03, "TourHomeDemand": 0.0,
        "GDP": 42852.96 * 87097, "BusinessFormation": 1450,
        "Marriages": 438, "Divorces": 13, "FamilyStability": 0.0296803653
    }
    
    for key, default_value in defaults.items():
        if key not in state:
            state[key] = default_value
    
    # Calculate infrastructure for baseline 2024 state
    # Use Continuity scenario parameters for baseline
    Pop_2024 = state.get("Pop", 87097)
    infra_config = deepcopy(INFRASTRUCTURE_CONFIG)
    infra_config["populations"]["CO"] = Pop_2024  # Use actual 2024 population
    
    try:
        infra_result = computeInfrastructureScenario("CO", config=infra_config)
        state["ElectricityPerCapita_kWh_year"] = infra_result["electricity"]["perCapita_kWh_year"]
        state["ElectricityDemand_kWh_year"] = infra_result["electricity"]["demand_kWh_year"]
        state["ElectricityCapacity_kW"] = infra_result["electricity"]["capacity_kW"]
        state["ElectricityRenewable_kW"] = infra_result["electricity"]["renewableCapacity_kW"]
        state["ElectricityFossil_kW"] = infra_result["electricity"]["fossilCapacity_kW"]
        state["WaterPerCapita_L_day"] = infra_result["water"]["perCapita_L_day"]
        state["WaterHousehold_m3_year"] = infra_result["water"]["householdDemand_m3_year"]
        state["WaterTotal_m3_year"] = infra_result["water"]["totalDemand_m3_year"]
        state["WaterSecurityIndex"] = infra_result["water"]["waterSecurityIndex"]
        state["HospitalBaselineBeds"] = infra_result["hospitals"]["baselineBeds"]
        state["HospitalRequiredBeds"] = infra_result["hospitals"]["requiredBeds"]
        state["HospitalDeltaBeds"] = infra_result["hospitals"]["deltaBeds"]
        # Use real student data from Current.json if available, otherwise use calculated
        if "SchoolStudents" not in state:
            state["SchoolStudents"] = infra_result["schools"]["students"]
        if "SchoolClassrooms" not in state:
            state["SchoolClassrooms"] = infra_result["schools"]["classrooms"]
        if "SchoolSchools" not in state:
            state["SchoolSchools"] = infra_result["schools"]["schools"]
        state["RoadTotalLength_km"] = infra_result["roads"]["totalLength_km"]
        state["RoadPerCapita_m"] = infra_result["roads"]["perCapita_m"]
    except Exception as e:
        print(f"Warning: Infrastructure calculation for baseline failed: {e}")
    
    return {
        "state": state,
        "params": {},  # Empty params for now
        "exog": {}     # Empty exog for now
    }

# ========== scenarioData.js generator ==========
def generate_scenariodata_js(model_dir):
    """Regenerate the timeseries blocks in scenarioData.js from the model JSON outputs."""
    js_path = model_dir.parent / "dashboard" / "public" / "js" / "scenarioData.js"
    if not js_path.exists():
        print(f"  scenarioData.js not found at {js_path} — skipping")
        return

    with js_path.open("r") as f:
        content = f.read()

    SECTION_START = "// Timeseries data for projected scenarios"
    SECTION_END   = "// Add timeseries data to scenarios"
    i0 = content.find(SECTION_START)
    i1 = content.find(SECTION_END)
    if i0 < 0 or i1 < 0:
        print("  Could not locate timeseries section in scenarioData.js — skipping")
        return

    scenario_map = {
        "continuity": "Continuity",
        "overgrowth": "Overgrowth",
        "degrowth":   "Degrowth",
        "density":    "Density",
    }

    blocks = []
    last_years = []
    last_ts_len = 0
    for js_key, file_key in scenario_map.items():
        ts_path = model_dir / f"{file_key}_timeseries.json"
        if not ts_path.exists():
            print(f"  {ts_path.name} missing — skipping")
            continue
        with ts_path.open("r") as f:
            ts = json.load(f)

        years = [str(row["Year"]) for row in ts]
        last_years = years
        last_ts_len = len(ts)
        skip = {"Year", "GDPpc_prev", "GDPpc_prev2", "HPrice_prev"}
        all_vars = [k for k in ts[0].keys() if k not in skip]

        series_lines = []
        for var in all_vars:
            vals = [row.get(var) or 0 for row in ts]
            series_lines.append(
                f"            {var}: {{ series: {json.dumps(vals)}, years: {json.dumps(years)} }}"
            )

        blocks.append(
            f"        const {js_key}Timeseries = {{\n"
            + ",\n".join(series_lines)
            + "\n        };"
        )

    year_range = f"{last_years[0]}-{last_years[-1]}" if last_years else "2025-2049"
    new_section = (
        f"// Timeseries data for projected scenarios ({year_range}) - using series/years format\n"
        + "\n".join(blocks)
        + "\n\n    "
    )

    with js_path.open("w") as f:
        f.write(content[:i0] + new_section + content[i1:])
    print(f"  scenarioData.js updated ({year_range}, {last_ts_len} years per scenario)")


# ========== main ==========
if __name__ == "__main__":
    here = Path(__file__).resolve().parent

    # Resolve input file robustly (handle casing and run-from-anywhere)
    candidates = [here / "Current.json", here / "current.json"]
    current_json_path = next((p for p in candidates if p.exists()), None)
    if current_json_path is None:
        candidates_cwd = [Path.cwd() / "Current.json", Path.cwd() / "current.json"]
        current_json_path = next((p for p in candidates_cwd if p.exists()), None)
    if current_json_path is None:
        raise FileNotFoundError("Could not locate Current.json/current.json next to CALCULATOR.py or in the current directory.")

    with current_json_path.open("r") as f:
        raw_data = json.load(f)

    # Transform the data structure
    current = transform_data_from_list_format(raw_data)
    here.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: Historical calibration (P1)
    #   Fit gTFP, GDPpc_gamma2, Income_a1 to 2010–2024 trajectory.
    #   Writes calibrated_params.json; calibrated values are then applied
    #   to current["params"] so all downstream runs use them.
    # ------------------------------------------------------------------
    print("Running historical calibration (scipy Nelder-Mead, 14 years × 3 params)...")
    calib = calibrate_historical_parameters(raw_data)
    (here / "calibrated_params.json").write_text(json.dumps(calib, indent=2))
    if calib.get("calibrated"):
        print(f"  gTFP={calib['gTFP']:.5f}  gamma2={calib['GDPpc_gamma2']:.5f}"
              f"  Income_a1={calib['Income_a1']:.5f}  RMSE={calib['rmse']:.6f}"
              f"  converged={calib['success']}")
        # Store calibrated values in current["params"]; simulate_path hoists these
        # as "_calib_*" base values inside calculate_dynamic_parameters so each
        # scenario still adds its own growth-rate adjustment on top.
        current.setdefault("params", {})
        current["params"]["gTFP"]         = calib["gTFP"]
        current["params"]["GDPpc_gamma2"] = calib["GDPpc_gamma2"]
        current["params"]["Income_a1"]    = calib["Income_a1"]
        # Also seed the private keys directly for the first call in simulate_path
        current["params"]["_calib_gTFP"]         = calib["gTFP"]
        current["params"]["_calib_GDPpc_gamma2"]  = calib["GDPpc_gamma2"]
        current["params"]["_calib_Income_a1"]     = calib["Income_a1"]
    else:
        print("  scipy unavailable or calibration failed — using prior parameter values.")

    # ------------------------------------------------------------------
    # Step 2: Scenario projections (with calibrated params + P3/P4 active)
    # ------------------------------------------------------------------
    print("Generating scenario projections (2025–2050)...")
    start_year = current.get("state", {}).get("Year", 2024)
    for name in ["Overgrowth", "Degrowth", "Continuity", "Density"]:
        ts, final_state = simulate_path(current, name, years=25, start_year=start_year)
        (here / f"{name}_timeseries.json").write_text(json.dumps(ts, indent=2))
        (here / f"{name}_final.json").write_text(json.dumps(final_state, indent=2))
        print(f"  {name}: Pop={final_state['Pop']:.0f}  GDPpc={final_state['GDPpc']:.0f}"
              f"  WLB={final_state['WLB']:.3f}  NatCov={final_state['NatCov']:.4f}")

    # Concise rollup for quick diffs
    rollup = {
        name: {
            "start": current["state"],
            "final": json.loads((here / f"{name}_final.json").read_text()),
        }
        for name in ["Overgrowth", "Degrowth", "Continuity", "Density"]
    }
    (here / "Scenario_Rollup.json").write_text(json.dumps(rollup, indent=2))

    # ------------------------------------------------------------------
    # Step 3: Monte Carlo uncertainty bounds (P2)
    #   500 samples per scenario; writes {Scenario}_mc_summary.json with
    #   p10/p50/p90 for 14 key variables over 2025–2035.
    # ------------------------------------------------------------------
    print("Running Monte Carlo (500 samples × 4 scenarios — may take ~30–60 s)...")
    for name in ["Overgrowth", "Degrowth", "Continuity", "Density"]:
        print(f"  {name}...", end=" ", flush=True)
        mc = monte_carlo_scenario(current, name, n_samples=500, seed=42)
        (here / f"{name}_mc_summary.json").write_text(json.dumps(mc, indent=2))
        # Print p10/p50/p90 GDPpc at final year as a sanity check
        gdp_mc = mc["variables"].get("GDPpc", {})
        p10 = gdp_mc.get("p10", [None])[-1]
        p50 = gdp_mc.get("p50", [None])[-1]
        p90 = gdp_mc.get("p90", [None])[-1]
        print(f"GDPpc 2050: p10={p10:.0f}  p50={p50:.0f}  p90={p90:.0f}")

    # ------------------------------------------------------------------
    # Step 4: Regenerate scenarioData.js timeseries blocks
    # ------------------------------------------------------------------
    generate_scenariodata_js(here)
    print("Done.")
