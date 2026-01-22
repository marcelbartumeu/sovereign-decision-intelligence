import json
from copy import deepcopy
from pathlib import Path
from infrastructure import computeInfrastructureScenario, INFRASTRUCTURE_CONFIG

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

    # exogenous/forced levels for this step (already interpolated upstream)
    Pop_target  = x("Pop_target", Pop_t)
    Tour_target = x("Tour_target", Tour_t)
    B_target    = x("B_target", B_t)
    force_pop   = x("force_pop", True)
    force_tour  = x("force_tour", True)
    force_build = x("force_build", True)

    Pop_t1  = Pop_target if force_pop else Pop_t
    Tour_t1 = Tour_target if force_tour else Tour_t
    B_t1    = B_target if force_build else B_t

    # Population model (still computed; scenario override wins if forced)
    gnat  = p("gnat", 0.002)
    Emp_star = p("Emp_star", 0.95)
    beta1 = p("beta1", 0.20); beta2 = p("beta2", 0.30); beta3 = p("beta3", 0.10)
    mig_capt = p("mig_capt", 0.0)

    gGDPpc = growth(GDPpc_t, s("GDPpc_prev", GDPpc_t))
    gHPrice = growth(HPrice_t, s("HPrice_prev", HPrice_t))
    Pop_model = Pop_t * (1 + gnat + beta1 * gGDPpc + beta2 * (Emp_t - Emp_star) - beta3 * gHPrice) + mig_capt
    Pop_next = Pop_t1 if force_pop else Pop_model

    NetMig = Pop_next - Pop_t
    alpha_fb = x("alpha_fb", p("alpha_fb", 1.0))
    FB_next = FB_t + alpha_fb * max(NetMig, 0.0)
    if NetMig < 0:
        FB_next = max(0.0, FB_t + NetMig)
    sFB_next = 0.0 if Pop_next <= 0 else FB_next / Pop_next

    # Access to Health (realistic scenario-dependent calculation)
    # Base access to health from 2024 data (0.922 = 92.2%)
    base_access = 0.922
    
    # Economic prosperity factor (higher GDP per capita = better healthcare access)
    economic_factor = (GDPpc_t - 45000.0) / 45000.0 * 0.05  # Economic impact on healthcare access
    
    # Population density factor (more people = potential strain on healthcare)
    density_factor = max(-0.05, (Pop_next - 87097.0) / 87097.0 * -0.02)  # Population pressure
    
    # Tourism factor (tourism can strain healthcare but also brings economic benefits)
    tourism_factor = (Tour_t1 - 8000000.0) / 8000000.0 * 0.01  # Tourism mixed effects
    
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

    # Employment rate (realistic calculation based on economic growth and population)
    # Base employment rate from 2024: 95%
    base_emp = 0.95
    
    # Economic growth factor (higher GDP growth = better employment)
    economic_emp_factor = (GDPpc_prov / 45000.0 - 1.0) * 0.1  # 10% employment impact per GDP doubling
    
    # Population growth factor (population growth can affect employment opportunities)
    pop_growth_factor = (Pop_next / 87097.0 - 1.0) * 0.05  # 5% employment impact per population doubling
    
    # Tourism factor (tourism creates jobs)
    tour_emp_factor = (Tour_t1 / 8000000.0 - 1.0) * 0.02  # 2% employment impact per tourism doubling
    
    # Calculate employment rate with realistic bounds
    Emp_next = clamp(base_emp + economic_emp_factor + pop_growth_factor + tour_emp_factor, 0.85, 0.98)

    # Employment calculation is now done above

    dEmp = Emp_next - Emp_t
    GDPpc_next = GDPpc_t * (1 + gTFP + gamma1 * dEmp + gamma2 * gTour)

    # Life Expectancy (realistic scenario-dependent calculation)
    # Base life expectancy from 2024 data (84.5 years)
    base_LE = 84.5
    
    # Scenario-based adjustments (additive rather than multiplicative to avoid extreme values)
    economic_boost = (GDPpc_next - 45000.0) / 45000.0 * 2.0  # GDP growth impact on healthcare
    health_strain = max(0, (Pop_next - 87097.0) / 87097.0 * 1.0)  # Population growth strain
    environmental_impact = max(-2.0, (AQI_t - 40.0) / 80.0 * -1.0)  # AQI impact
    tourism_impact = (Tour_t1 - 8000000.0) / 8000000.0 * 0.5  # Tourism mixed effects
    
    # Calculate life expectancy with scenario-specific adjustments
    LE_next = clamp(base_LE + economic_boost - health_strain + environmental_impact + tourism_impact, 75, 90)

    # Income & Salary (realistic relationship to GDP)
    a0 = p("Income_a0", 0.0); a1 = p("Income_a1", 0.6); a2 = p("Income_a2", 0.0)
    Income_next = a0 + a1 * GDPpc_next + a2 * Emp_next

    # Salary calculation (consistent with income growth)
    # Base salary-to-income ratio from 2024: 30,852 / 55,534 = 0.556
    salary_ratio = p("Salary_ratio", 0.556)  # Salary-to-income ratio
    # Salary is monthly (like historical data: 2,571 per month)
    # Income is annual, so convert: Salary_monthly = (Salary_ratio * Income_annual) / 12
    Salary_next = (salary_ratio * Income_next) / 12.0

    # Work–Life Balance (realistic scenario-dependent calculation)
    # Base work-life balance from 2024 data (0.6 = 60%)
    base_WLB = 0.6
    
    # Economic prosperity factor (higher income = better work-life balance)
    economic_factor = (Income_next - 40000.0) / 40000.0 * 0.1  # Income impact on WLB
    
    # Population density factor (more people = more work pressure)
    density_factor = max(-0.1, (Pop_next - 87097.0) / 87097.0 * -0.05)  # Population pressure
    
    # Tourism factor (tourism jobs can be seasonal and stressful)
    tourism_factor = (Tour_t1 - 8000000.0) / 8000000.0 * -0.05  # Tourism job pressure
    
    # Employment factor (high employment = more job security and better conditions)
    employment_factor = (Emp_next - 0.95) * 0.2  # Employment rate impact
    
    # Calculate work-life balance with realistic adjustments
    WLB_next = clamp(base_WLB + economic_factor + density_factor + tourism_factor + employment_factor, 0.3, 0.8)

    # Business Formation (scales with population and economic conditions)
    # Base business formation per capita from 2024 data
    base_business_per_capita = 1450.0 / 87097.0  # ~0.0166 businesses per person
    
    # Scale with population (more people = more businesses)
    pop_scaling = Pop_next / 87097.0  # Scale relative to 2024 population
    
    # Economic growth factor (higher GDP/income = more business formation)
    gdp_scaling = GDPpc_next / 45000.0  # Scale relative to 2024 GDP per capita
    
    # Tourism factor (more tourism = more business opportunities)
    tour_scaling = Tour_t1 / 8000000.0  # Scale relative to 2024 tourism
    
    # Combine factors with weights
    BusinessFormation_next = 1450.0 * pop_scaling * (0.7 + 0.2 * gdp_scaling + 0.1 * tour_scaling)

    # Family Stability Metrics (realistic scenario-dependent calculations)
    # Base values from 2024 data
    base_marriages = 438
    base_divorces = 13
    base_family_stability = 0.0296803653
    
    # Marriages scale with population and economic prosperity
    marriage_rate = base_marriages / 87097.0  # Marriages per capita
    Marriages_next = int(round(marriage_rate * Pop_next * (0.8 + 0.2 * gdp_scaling)))
    
    # Divorces scale with population (divorce rate should remain relatively constant per capita)
    divorce_rate = base_divorces / 87097.0  # Divorces per capita
    Divorces_next = int(round(divorce_rate * Pop_next))
    
    # Family stability proxy (meaningful calculation based on marriage-to-divorce ratio and economic factors)
    if Marriages_next > 0 and Divorces_next > 0:
        # Calculate marriage-to-divorce ratio
        marriage_divorce_ratio = Marriages_next / Divorces_next
        
        # Base family stability from 2024 data (2.97%)
        base_stability = 0.0296803653
        
        # Economic prosperity factor (higher GDP = better family stability)
        economic_factor = (gdp_scaling - 1.0) * 0.1  # Economic growth impact
        
        # Population density factor (higher density can stress families)
        density_factor = max(-0.05, (Pop_next - 87097.0) / 87097.0 * -0.02)
        
        # Marriage rate factor (higher marriage rates indicate better family formation)
        marriage_rate_factor = (Marriages_next / Pop_next) / (base_marriages / 87097.0) - 1.0
        marriage_rate_factor = marriage_rate_factor * 0.05
        
        # Divorce rate factor (lower divorce rates indicate better family stability)
        divorce_rate_factor = 1.0 - (Divorces_next / Pop_next) / (base_divorces / 87097.0)
        divorce_rate_factor = max(0, divorce_rate_factor * 0.1)
        
        # Calculate family stability proxy (should range 0-1, representing percentage)
        FamilyStability_next = clamp(
            base_stability + economic_factor + density_factor + marriage_rate_factor + divorce_rate_factor,
            0.01,  # Minimum 1%
            0.6    # Maximum 60% (realistic upper bound based on historical data)
        )
    else:
        FamilyStability_next = base_family_stability

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
    h0 = p("H_h0", 0.0); h1 = p("H_h1", 0.3); h2 = p("H_h2", 1.5); h3 = p("H_h3", 1.0); h4 = p("H_h4", 0.8)
    HPrice_next = h0 + h1 * Income_next - h2 * (B_next / max(Pop_next, 1)) - h3 * s("Rate", 0.03) + h4 * s("TourHomeDemand", 0.0)
    
    # Housing affordability as percentage of median household income spent on housing
    # Based on corrected data: 2024 = 28.79843554
    # Calculate as actual percentage of income spent on housing
    base_afford = 28.79843554  # 2024 baseline (corrected data)
    
    if Income_next > 0 and HPrice_next > 0:
        # Calculate actual monthly housing cost as percentage of monthly income
        monthly_income = Income_next / 12
        monthly_housing_cost = HPrice_next / 12  # Annual housing cost / 12 months
        
        # Calculate percentage of income spent on housing
        Afford_next = min(60.0, (monthly_housing_cost / monthly_income) * 100.0)  # Cap at 60%
    else:
        Afford_next = base_afford

    # Natural coverage (realistic calculation based on Andorra's physical constraints)
    # Andorra total area: 468 km², buildable area: 65.41 km²
    # 2024: 10,645 buildings in 30.936 km² (344.1 buildings/km²)
    
    total_area = 468.0  # km²
    buildable_area = 65.41  # km²
    buildings_per_km2 = 344.1  # buildings per km² (from 2024 data)
    
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
    
    # Economic scaling (GDP per capita impact)
    economic_scaling = GDPpc_next / 45000.0
    
    # Tourism impact (minimal)
    tour_scaling = Tour_t1 / 8000000.0
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
    
    # Economic activity scaling (higher GDP per capita enables more renewable investment)
    gdp_scaling = GDPpc_next / 45000.0  # GDP scaling factor
    
    # Population and tourism energy demand scaling
    pop_tour_scaling = (Pop_next + Tour_t1) / (87097.0 + 8000000.0)  # Combined scaling
    
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
    
    # Tourism impact on air quality (more tourism = more traffic/activity = slightly worse air)
    AQI_chi = p("AQI_chi", 0.15)  # Tourism impact parameter
    tour_ratio = Tour_t1 / 9646656.0  # Normalize to 2024 tourism level
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
    
    # 2024 baseline values for scaling
    base_pop_2024 = 87097.0
    base_gdp_2024 = 45000.0
    base_tour_2024 = 9646656.0  # Actual 2024 tourism value
    
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
    
    # Natural coverage cooling effect (more nature = cooler)
    natural_cooling = (NatCov_next - 0.9359) * -2.0  # -2°C per 10% natural coverage increase
    
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
        "B": B_next, "HPrice": HPrice_next, "HPrice_prev": HPrice_t, "Afford": Afford_next,  # Afford = Percentage of income spent on housing, HPrice_prev for growth calculation
        "NatCov": NatCov_next, "CO2pc": CO2pc_next, "CO2_total": CO2_total_next,
        "Ren": Ren_next, "AQI": AQI_next, "Water": Water_next,
        "Temp": Temp_next, "Tour": Tour_t1,
        "GDP": GDPpc_next * Pop_next,
        "Marriages": Marriages_next, "Divorces": Divorces_next, "FamilyStability": FamilyStability_next,
        "Emp": Emp_next,  # Employment rate
        **infrastructure  # Add all infrastructure fields
    }
    return {"state": out_state, "params": P, "exog": X}

# ========== dynamic parameter calculation ==========
def calculate_dynamic_parameters(scenario_name, current_state):
    """Calculate scenario-specific parameters based on population, tourism, and destination assumptions."""
    
    # Load scenario assumptions
    here = Path(__file__).resolve().parent
    scenario_path = here.parent / "conf" / "scenarios" / f"{scenario_name.lower()}.json"
    
    if scenario_path.exists():
        with scenario_path.open("r") as f:
            scenario_config = json.load(f)
        assumptions = scenario_config.get("assumptions", {})
    else:
        # Fallback assumptions if config file doesn't exist
        if scenario_name == "Overgrowth":
            assumptions = {"population_growth_rate": 0.02, "tourism_growth_rate": 0.03, "co2_intensity_change": 0.005}
        elif scenario_name == "Degrowth":
            assumptions = {"population_growth_rate": -0.005, "tourism_growth_rate": -0.01, "co2_intensity_change": -0.01}
        else:  # Continuity - based on historical trends (2014-2024)
            # Historical annual growth rates: Pop 2.126%, Tour 2.152%
            # Using these realistic rates for "what if we continued the same trend"
            assumptions = {"population_growth_rate": 0.0213, "tourism_growth_rate": 0.0215, "co2_intensity_change": -0.005}
    
    pop_growth_rate = assumptions.get("population_growth_rate", 0.005)
    tour_growth_rate = assumptions.get("tourism_growth_rate", 0.01)
    co2_intensity_change = assumptions.get("co2_intensity_change", -0.005)
    
    # Current state values
    Pop0 = current_state.get("Pop", 87097)
    Tour0 = current_state.get("Tour", 8000000)
    GDPpc0 = current_state.get("GDPpc", 45000)
    
    # Calculate dynamic parameters based on scenario characteristics
    params = {}
    
    # Population-related parameters
    params["gnat"] = pop_growth_rate * 0.1  # Natural growth scaled down
    params["beta1"] = 0.15 + abs(pop_growth_rate) * 5  # GDP sensitivity to population growth
    params["beta2"] = 0.25 + abs(pop_growth_rate) * 2  # Employment sensitivity
    params["beta3"] = 0.08 + abs(pop_growth_rate) * 3  # Housing price sensitivity
    
    # Tourism-related parameters
    params["gamma2"] = 0.05 + tour_growth_rate * 2  # GDP sensitivity to tourism
    params["theta_tour_load"] = 0.2 + tour_growth_rate * 5  # Health system load from tourism
    params["AQI_chi"] = 0.15 + tour_growth_rate * 3  # Tourism impact on air quality
    
    # Economic parameters based on growth assumptions
    growth_factor = (pop_growth_rate + tour_growth_rate) / 2
    params["gTFP"] = 0.005 + growth_factor * 0.1  # Total factor productivity (conservative for developed economies)
    params["Income_a1"] = 1.234 + growth_factor * 0.1  # Income sensitivity to GDP (maintains 2024 ratio)
    params["Salary_ratio"] = 0.556 + growth_factor * 0.05  # Salary-to-income ratio (maintains 2024 ratio: 30,852/55,534 = 0.556)
    
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
    else:  # continuity
        params["Temp_scenario_factor"] = 0.0  # Baseline scenario
    
    # Water consumption scenario factors
    if scenario_name == "overgrowth":
        params["Water_scenario_factor"] = 1.2  # Higher water consumption from intense development and tourism
    elif scenario_name == "degrowth":
        params["Water_scenario_factor"] = 0.8  # Lower water consumption from reduced activity
    else:  # continuity
        params["Water_scenario_factor"] = 1.0  # Baseline scenario
    
    # Renewable energy investment scenario factors
    if scenario_name == "overgrowth":
        params["Ren_investment_factor"] = 1.3  # Higher renewable investment from economic growth and energy needs
    elif scenario_name == "degrowth":
        params["Ren_investment_factor"] = 0.9  # Lower renewable investment from reduced economic activity
    else:  # continuity
        params["Ren_investment_factor"] = 1.1  # Moderate renewable investment growth
    
    return params

# ========== scenario builders (targets only) ==========
def scenario_targets(current_state, scenario_name):
    Pop0 = current_state["Pop"]; B0 = current_state["B"]; Tour0 = current_state["Tour"]
    ppb0 = (Pop0 / B0) if B0 > 0 else 0.0

    # Calculate baseline tourists-per-person ratio from 2024 data
    # This ratio is used to make tourism proportional to population in all scenarios
    tourists_per_person_2024 = Tour0 / max(Pop0, 1e-9)

    if scenario_name == "Overgrowth":
        Pop_T = 200_000
        # Tourism grows proportionally with population, using the baseline ratio
        Tour_T = int(round(Pop_T * tourists_per_person_2024))
        # same density every year → B follows Pop each year at ppb0
        def B_target(Pop_t): 
            return int(round(Pop_t / max(ppb0, 1e-9)))
        alpha_fb = 1.0
        return Pop_T, Tour_T, B_target, alpha_fb

    if scenario_name == "Degrowth":
        Pop_T = 50_000
        # Tourism shrinks proportionally with population, using the baseline ratio
        Tour_T = int(round(Pop_T * tourists_per_person_2024))
        # buildings constant across all years
        def B_target(_Pop_t): 
            return B0
        alpha_fb = 1.0  # departures handled in step_next
        return Pop_T, Tour_T, B_target, alpha_fb

    if scenario_name == "Continuity":
        # Continuity: keep tourism proportional to population, using the
        # empirically observed 2024 ratio of tourists per resident.
        #
        # Historical data (2014–2024) shows tourism and population moving
        # closely together; instead of assuming an independent tourism
        # growth rate, we:
        #   1) project population with the historically‑based 2.126% rate
        #   2) set tourists as: Tour_t ≈ (Tour_2024 / Pop_2024) * Pop_t
        #
        # This guarantees that in the continuity scenario tourism grows
        # *proportionally* with population instead of being an arbitrary
        # separate target.
        Pop_T = int(round(Pop0 * (1.02126 ** 11)))  # ~109,780
        Tour_T = int(round(Pop_T * tourists_per_person_2024))

        # Maintain current density (ppb0) - buildings grow with population
        def B_target(Pop_t):
            return int(round(Pop_t / max(ppb0, 1e-9)))
        alpha_fb = 1.0
        return Pop_T, Tour_T, B_target, alpha_fb

    raise ValueError("Unknown scenario")

# ========== simulate multi-year path ==========
def simulate_path(current, scenario_name, years=10, start_year=None):
    base = deepcopy(current)
    base.setdefault("state", {})
    base.setdefault("params", {})
    base.setdefault("exog", {})

    # Calculate dynamic parameters for this scenario
    dynamic_params = calculate_dynamic_parameters(scenario_name, base["state"])
    base["params"].update(dynamic_params)

    year0 = start_year if start_year is not None else int(base["state"].get("Year", 2025))

    S0 = deepcopy(base["state"])
    Pop0, Tour0, B0 = S0.get("Pop", 0), S0.get("Tour", 0), S0.get("B", 0)

    Pop_T, Tour_T, B_target_fn, alpha_fb = scenario_targets(S0, scenario_name)

    # All scenarios now enforce a proportional relationship between tourism
    # and population over the whole path, using the baseline tourists‑per‑resident
    # ratio from 2024. This ensures tourism grows/shrinks proportionally with
    # population rather than being an arbitrary independent target.
    tourists_per_person_2024 = Tour0 / max(Pop0, 1e-9)

    timeline = []
    curr = deepcopy(base)

    for t in range(1, years + 1):
        Pop_tgt  = interp_linear(Pop0,  Pop_T,  t, years)

        # Tourism grows/shrinks strictly in proportion to population, using
        # the empirically observed baseline ratio from 2024.
        Tour_tgt = tourists_per_person_2024 * Pop_tgt
        B_tgt    = B_target_fn(Pop_tgt)

        ex = deepcopy(curr.get("exog", {}))
        ex.update({
            "Pop_target":  Pop_tgt,
            "Tour_target": Tour_tgt,
            "B_target":    B_tgt,  # Keep as reference but don't force
            "force_pop": True, "force_tour": True, "force_build": False,  # Changed to False to use formula-based calculation
            "alpha_fb": alpha_fb,
            "scenario_name": scenario_name,  # Pass scenario name for infrastructure calculations
            "target_year": year0 + t  # Pass target year for gradual factor calculations
        })
        curr["exog"] = ex

        # one-year step
        res = step_next(curr)

        # stamp the year
        res["state"]["Year"] = year0 + t

        # store
        timeline.append(deepcopy(res["state"]))

        # advance state
        curr["state"] = deepcopy(res["state"])
        # keep params/exog carried forward except per-step overrides we recompute anyway
        curr["params"] = curr.get("params", {})
        curr["exog"] = curr.get("exog", {})

    return timeline, timeline[-1]

# ========== data transformation ==========
def transform_data_from_list_format(data_list):
    """Transform list-based JSON data to the expected dictionary format."""
    # Skip the header row (index 0) and category rows
    data_rows = [row for row in data_list[1:] if row.get("Unnamed: 0") and row["Unnamed: 0"] not in ["SOCIAL", "ECONOMIC", "ENVIRONMENTAL", "BUILDINGS", "HEALTH"]]
    
    # Extract the latest year's data (2024)
    state = {}
    for row in data_rows:
        metric_name = row["Unnamed: 0"]
        value_2024 = row.get("2024")
        if value_2024 is not None:
            # Map metric names to state keys
            if "Population Growth" in metric_name:
                state["Pop"] = value_2024
            elif "Life expectency" in metric_name:
                state["LE"] = value_2024
            elif "GDP per capita" in metric_name:
                state["GDPpc"] = value_2024
            elif "Employment rate" in metric_name:
                state["Emp"] = value_2024
            elif "Housing Price" in metric_name:
                state["HPrice"] = value_2024
            elif "Tourism" in metric_name or "Tourist" in metric_name:
                state["Tour"] = value_2024
            elif "Number of buildings" in metric_name:
                state["B"] = value_2024
            elif "Foreign Born" in metric_name:
                state["ForeignBorn"] = value_2024
            elif "Work-Life Balance" in metric_name:
                state["WLB"] = value_2024
            elif "Access to Health" in metric_name:
                state["Access"] = value_2024
            elif "Median Household Income" in metric_name:
                state["Income"] = value_2024 * 12  # Convert monthly median household income to annual
            elif "Median House Price" in metric_name:
                state["HPrice"] = value_2024 * 12 * 2  # Convert monthly to annual and multiply by 2 people per household
            elif "Average Monthly Salary" in metric_name:
                state["Salary"] = value_2024  # Salary is monthly (2,571 in 2024)
            elif "Affordability" in metric_name:
                state["Afford"] = value_2024 * 100  # Convert to percentage
            elif "Natural Coverage" in metric_name:
                state["NatCov"] = value_2024
            elif "CO₂ Emissions per Capita" in metric_name:
                # This is actually total CO2 emissions in KT, not per capita
                # Convert to per capita: total CO2 (KT) / population
                state["CO2_total"] = value_2024 * 1000  # Convert KT to tons
                state["CO2pc"] = (value_2024 * 1000) / 87097  # Calculate per capita
            elif "Renewables" in metric_name:
                state["Ren"] = value_2024
            elif "Air Quality" in metric_name:
                # AQI values in Current.json are stored as integers (6015.0 instead of 6.015)
                # Divide by 1000 to get the actual AQI value
                state["AQI"] = value_2024 / 1000.0 if value_2024 > 100 else value_2024
            elif "Water Consumption" in metric_name or "Water Consumption a day" in metric_name:
                state["Water"] = value_2024
            elif "Temperature" in metric_name:
                state["Temp"] = value_2024
            elif "Business Formation" in metric_name:
                state["BusinessFormation"] = value_2024
            elif "Marriages" in metric_name:
                state["Marriages"] = value_2024
            elif "Divorces" in metric_name:
                state["Divorces"] = value_2024
            elif "Family stability proxy" in metric_name:
                state["FamilyStability"] = value_2024
            elif "School Students" in metric_name:
                # Use real student data from Current.json
                state["SchoolStudents"] = value_2024
            elif "School Classrooms" in metric_name:
                # Use real classroom data from Current.json
                state["SchoolClassrooms"] = value_2024
            elif "School Schools" in metric_name:
                # Use real school data from Current.json
                state["SchoolSchools"] = value_2024
    
    # Set Year to 2024
    state["Year"] = 2024
    
    # Set default values for missing metrics
    defaults = {
        "Pop": 87097, "GDPpc": 45000, "Emp": 0.95, "HPrice": 15992.808, "Tour": 8000000,
        "B": 10645, "ForeignBorn": 30000, "LE": 84.5, "WLB": 0.6, "Access": 0.922,
        "Income": 55533.6, "Salary": 2571, "Afford": 28.79843554, "NatCov": 0.9359, "CO2pc": 5.396, "CO2_total": 470000,  # Income = Median household income (annual), Salary = Average monthly salary (2,571 in 2024), NatCov = 93.59%, CO2pc = 5.396 tons per capita (from corrected current.json), CO2_total = 470KT = 470,000 tons
        "Ren": 0.931, "AQI": 8.40, "Water": 53655, "Temp": 7.46,  # AQI = 8.40 (actual 2024 value, excellent mountain air quality)
        "Beds": 2000, "PriceIdx": 1.0, "GlobalTravel": 1.0, "LaborShare": 0.55,
        "Rate": 0.03, "TourHomeDemand": 0.0,
        "GDP": 45000 * 87097, "BusinessFormation": 1450,
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

# ========== main ==========
if __name__ == "__main__":
    here = Path(__file__).resolve().parent

    # Resolve input file robustly (handle casing and run-from-anywhere)
    candidates = [here / "Current.json", here / "current.json"]
    current_json_path = next((p for p in candidates if p.exists()), None)
    if current_json_path is None:
        # Fallback to CWD if someone insists on running from the file's folder incorrectly named
        candidates_cwd = [Path.cwd() / "Current.json", Path.cwd() / "current.json"]
        current_json_path = next((p for p in candidates_cwd if p.exists()), None)
    if current_json_path is None:
        raise FileNotFoundError("Could not locate Current.json/current.json next to CALCULATOR.py or in the current directory.")

    with current_json_path.open("r") as f:
        raw_data = json.load(f)
    
    # Transform the data structure
    current = transform_data_from_list_format(raw_data)

    # Ensure output directory (script directory) exists
    here.mkdir(parents=True, exist_ok=True)

    for name in ["Overgrowth", "Degrowth", "Continuity"]:
        ts, final_state = simulate_path(current, name, years=11, start_year=current.get("state", {}).get("Year", 2025))
        (here / f"{name}_timeseries.json").write_text(json.dumps(ts, indent=2))
        (here / f"{name}_final.json").write_text(json.dumps(final_state, indent=2))

    # Optional concise rollup for quick diffs:
    rollup = {
        "Overgrowth": {"start": current["state"], "final": json.loads((here / "Overgrowth_final.json").read_text())},
        "Degrowth": {"start": current["state"], "final": json.loads((here / "Degrowth_final.json").read_text())},
        "Continuity": {"start": current["state"], "final": json.loads((here / "Continuity_final.json").read_text())},
    }
    (here / "Scenario_Rollup.json").write_text(json.dumps(rollup, indent=2))
