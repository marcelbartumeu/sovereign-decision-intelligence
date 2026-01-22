"""
Infrastructure Calculation Module
Calculates infrastructure requirements for different population scenarios.
"""

# ========== Configuration Constants ==========
INFRASTRUCTURE_CONFIG = {
    # Baseline population (2024)
    "P0": 87097,
    
    # Scenario populations
    # Note: CO (Continuity) is not included here because CALCULATOR.py always overrides
    # it with the actual population value each year. These defaults are for standalone testing only.
    "populations": {
        "OG": 200000,  # Overgrowth
        "DG": 50000    # Degrowth
    },
    
    # Electricity constants
    "electricity": {
        "e_pc_0": 3000,  # kWh/person/year (baseline)
        "f_E": {
            "OG": 1.0,
            "CO": 1.0,
            "DG": 1.0
        },
        "CF": 0.5,  # capacity factor
        "H": 8760,  # hours/year
        "r": {  # renewable share
            "OG": 0.6,
            "CO": 0.5,
            "DG": 0.5
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
            "DG": 2.5
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
        scenario: One of "OG" (Overgrowth), "CO" (Continuity), "DG" (Degrowth)
        config: Optional configuration dict. If None, uses INFRASTRUCTURE_CONFIG.
    
    Returns:
        Dictionary with infrastructure calculations for the scenario.
    """
    if config is None:
        config = INFRASTRUCTURE_CONFIG
    
    # Validate scenario
    if scenario not in ["OG", "CO", "DG"]:
        raise ValueError(f"Invalid scenario: {scenario}. Must be 'OG', 'CO', or 'DG'")
    
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


# ========== Example usage and testing ==========
if __name__ == "__main__":
    # Test individual scenario
    print("Testing Overgrowth scenario:")
    og_result = computeInfrastructureScenario("OG")
    print(f"Population: {og_result['population']:,}")
    print(f"Electricity demand: {og_result['electricity']['demand_kWh_year']:,.0f} kWh/year")
    print(f"Total capacity: {og_result['electricity']['capacity_kW']:,.2f} kW")
    print(f"Water total demand: {og_result['water']['totalDemand_m3_year']:,.0f} m³/year")
    print(f"Required beds: {og_result['hospitals']['requiredBeds']:.1f}")
    print(f"Students: {og_result['schools']['students']:,.0f}")
    print(f"Schools needed: {og_result['schools']['schools']:.1f}")
    print()
    
    # Test all scenarios
    print("Testing all scenarios:")
    all_results = computeAllInfrastructureScenarios()
    for scenario, result in all_results.items():
        print(f"\n{scenario} ({result['scenario']}):")
        print(f"  Population: {result['population']:,}")
        print(f"  Electricity capacity: {result['electricity']['capacity_kW']:,.2f} kW")
        print(f"  Water security index: {result['water']['waterSecurityIndex']:.3f}")
        print(f"  Delta beds: {result['hospitals']['deltaBeds']:+.1f}")
        print(f"  Schools: {result['schools']['schools']:.1f}")
