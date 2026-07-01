"""
Synthetic population generator.

Samples demographic attribute bundles from empirically grounded distributions
for the AOI. Each bundle becomes the input to the LLM preference generation step.

The synthesiser uses:
  1. WorldPop age/sex structure for marginal age/sex distributions
  2. Country-specific nationality mix (from census or Estadística data)
  3. Occupation-income joint distributions (from labour statistics or ISCO proxy)
  4. Household type distributions (from census household tables)
  5. Spatial assignment weighted by H3 cell population density

Population synthesis methodology
─────────────────────────────────
This implements a simplified version of the Iterative Proportional Fitting (IPF)
approach used in microsimulation (Lovelace & Dumont 2016). Full IPF requires
a seed matrix and marginal totals from census tables — implemented as a stub
here for extensibility. The current version uses independent marginal sampling,
which is sufficient for agent generation without a full microsimulation engine.

Reference: Lovelace R. & Dumont M. (2016) Spatial Microsimulation with R.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class DemographicProfile:
    """
    A single synthetic agent's demographic attributes.
    These are the inputs to the LLM preference generation step.
    """
    agent_id: str
    age: int
    gender: str                 # M | F
    nationality: str
    occupation: str
    income_bracket: str         # precarious | low | lower_middle | middle | upper_middle | comfortable | wealthy
    household_type: str
    marital_status: str                # single | married
    num_children: int                  # number of dependent children in household
    h3_cell: str | None         # assigned H3 cell (if spatial placement is done)
    years_in_aoi: float         # years of residence in the AOI
    education_level: str        # no_formal | primary | secondary | tertiary | postgrad
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_prompt_string(self) -> str:
        """Compact demographic description for LLM injection."""
        return (
            f"Age: {self.age}, Gender: {self.gender}, Nationality: {self.nationality}, "
            f"Occupation: {self.occupation}, Income: {self.income_bracket}, "
            f"Household: {self.household_type}, Years in AOI: {self.years_in_aoi:.1f}, "
            f"Marital status: {self.marital_status}, Children: {self.num_children}, "
            f"Education: {self.education_level}"
        )


# ── Andorra-specific distributions ───────────────────────────────────────────
# Source: Estadística d'Andorra (SAIG) 2023; AEA labour force data 2022

ANDORRA_NATIONALITY_DIST = {
    "Andorran":   0.356,
    "Spanish":    0.335,
    "Portuguese": 0.171,
    "French":     0.066,
    "Other_EU":   0.036,
    "Non_EU":     0.036,
}

# Occupation × Nationality joint probability (simplified, row sums to 1 per nationality)
# Source: AEA Enquesta sobre condicions de vida 2022
OCCUPATION_BY_NATIONALITY: dict[str, dict[str, float]] = {
    "Andorran": {
        "public_sector":       0.25,
        "business_owner":      0.18,
        "finance_professional":0.10,
        "teacher":             0.08,
        "retail_manager":      0.10,
        "retired":             0.15,
        "student":             0.08,
        "other_professional":  0.06,
    },
    "Spanish": {
        "retail_worker":       0.20,
        "hospitality_worker":  0.15,
        "cross_border_worker": 0.15,
        "school_administrator":0.08,
        "real_estate_agent":   0.07,
        "construction_worker": 0.10,
        "finance_professional":0.08,
        "other_service":       0.17,
    },
    "Portuguese": {
        "retail_worker":       0.25,
        "construction_worker": 0.20,
        "hotel_housekeeper":   0.15,
        "restaurant_worker":   0.15,
        "domestic_worker":     0.10,
        "supermarket_worker":  0.10,
        "other_service":       0.05,
    },
    "French": {
        "finance_analyst":     0.20,
        "architect":           0.10,
        "teacher":             0.12,
        "hospitality_worker":  0.15,
        "retail_professional": 0.15,
        "other_professional":  0.28,
    },
    "Other_EU": {
        "seasonal_ski_worker": 0.30,
        "hospitality_worker":  0.25,
        "retail_worker":       0.20,
        "other_service":       0.25,
    },
    "Non_EU": {
        "restaurant_worker":   0.25,
        "domestic_worker":     0.25,
        "construction_worker": 0.20,
        "retail_worker":       0.15,
        "other_service":       0.15,
    },
}

# Income bracket conditional on occupation (simplified)
INCOME_BY_OCCUPATION: dict[str, str] = {
    "public_sector":        "middle",
    "business_owner":       "comfortable",
    "finance_professional": "upper_middle",
    "finance_analyst":      "upper_middle",
    "architect":            "comfortable",
    "teacher":              "middle",
    "retail_manager":       "middle",
    "school_administrator": "middle",
    "real_estate_agent":    "comfortable",
    "other_professional":   "middle",
    "retail_professional":  "lower_middle",
    "retired":              "middle",
    "student":              "low",
    "cross_border_worker":  "middle",
    "retail_worker":        "lower_middle",
    "hospitality_worker":   "lower_middle",
    "construction_worker":  "precarious",
    "hotel_housekeeper":    "precarious",
    "restaurant_worker":    "precarious",
    "domestic_worker":      "precarious",
    "supermarket_worker":   "lower_middle",
    "seasonal_ski_worker":  "precarious",
    "other_service":        "lower_middle",
}

HOUSEHOLD_TYPES = [
    ("single",               0.28),
    ("couple_no_kids",       0.18),
    ("couple_with_child",    0.22),
    ("single_parent",        0.08),
    ("couple_empty_nest",    0.12),
    ("shared_housing",       0.08),
    ("family_home",          0.04),
]

EDUCATION_BY_AGE: dict[str, dict[str, float]] = {
    "young":  {"secondary": 0.30, "tertiary": 0.45, "postgrad": 0.15, "primary": 0.10},
    "middle": {"secondary": 0.35, "tertiary": 0.35, "postgrad": 0.10, "primary": 0.20},
    "older":  {"secondary": 0.40, "tertiary": 0.25, "postgrad": 0.05, "primary": 0.25, "no_formal": 0.05},
}

ANDORRA_PARISHES = [
    ("Andorra_la_Vella",     0.25),
    ("Escaldes-Engordany",   0.23),
    ("Sant_Julia_de_Loria",  0.13),
    ("Encamp",               0.13),
    ("La_Massana",           0.11),
    ("Ordino",               0.08),
    ("Canillo",              0.07),
]


class PopulationSynthesizer:
    """
    Generates synthetic demographic profiles for an AOI population.

    Parameters
    ----------
    nationality_dist  : {nationality: probability} — marginal nationality distribution
    age_sex_structure : AgeSexStructure from WorldPop (or fallback)
    rng_seed          : Random seed for reproducibility
    """

    def __init__(
        self,
        nationality_dist: dict[str, float],
        age_sex_structure,
        occupation_by_nat: dict[str, dict[str, float]] | None = None,
        rng_seed: int = 42,
        household_dist: dict[str, float] | None = None,
        children_dist: dict[str, float] | None = None,
    ):
        self.nat_dist = nationality_dist
        self.age_sex = age_sex_structure
        self.occ_by_nat = occupation_by_nat or OCCUPATION_BY_NATIONALITY
        self.rng = np.random.default_rng(rng_seed)
        self.household_dist = household_dist or {h: p for h, p in HOUSEHOLD_TYPES}
        self.children_dist = children_dist or {"0": 1.0}

    def _sample_nationality(self) -> str:
        nats = list(self.nat_dist.keys())
        probs = list(self.nat_dist.values())
        return self.rng.choice(nats, p=np.array(probs) / sum(probs))

    def _sample_occupation(self, nationality: str) -> str:
        dist = self.occ_by_nat.get(nationality, self.occ_by_nat.get("Other_EU", {}))
        if not dist:
            return "other_service"
        occs = list(dist.keys())
        probs = list(dist.values())
        return self.rng.choice(occs, p=np.array(probs) / sum(probs))

    def _sample_household(self, age: int, nationality: str) -> str:
        types = list(self.household_dist.keys())
        probs = list(self.household_dist.values())
        # Adjust for age - older agents less likely to have young children
        if age > 55 and "single_with_children" in types:
            idx = types.index("single_with_children")
            probs[idx] *= 0.2
        if age > 55 and "couple_with_children" in types:
            idx = types.index("couple_with_children")
            probs[idx] *= 0.2
        if age < 25 and "couple_with_children" in types:
            idx = types.index("couple_with_children")
            probs[idx] *= 0.3
        probs = np.array(probs) / sum(probs)
        return self.rng.choice(types, p=probs)

    def _sample_marital_status(self, household_type: str) -> str:
        """Derive marital status directly from household type."""
        return "married" if household_type.startswith("couple") else "single"

    def _sample_num_children(self, household_type: str) -> int:
        """Sample number of children, only for household types that include children."""
        if "with_children" not in household_type:
            return 0
        keys = [k for k in self.children_dist.keys() if k != "0"]
        if not keys:
            return 1
        probs = [self.children_dist[k] for k in keys]
        probs = np.array(probs) / sum(probs)
        choice = self.rng.choice(keys, p=probs)
        return 3 if choice == "3+" else int(choice)

    def _sample_education(self, age: int) -> str:
        if age < 35:
            dist = EDUCATION_BY_AGE["young"]
        elif age < 55:
            dist = EDUCATION_BY_AGE["middle"]
        else:
            dist = EDUCATION_BY_AGE["older"]
        keys = list(dist.keys())
        probs = list(dist.values())
        return self.rng.choice(keys, p=np.array(probs) / sum(probs))

    def _sample_years_in_aoi(self, nationality: str, age: int) -> float:
        if nationality == "Andorran":
            return float(age)  # born there (approximately)
        # Log-normal distribution — most immigrants are recent, some are long-term
        mean_years = {"Spanish": 10.0, "Portuguese": 8.0, "French": 7.0}.get(nationality, 4.0)
        raw = self.rng.lognormal(mean=np.log(mean_years), sigma=0.8)
        return float(min(raw, age - 18))  # can't have been there longer than adult life

    def generate(self, n: int, h3_cells: list[str] | None = None,
                 cell_weights: list[float] | None = None) -> list[DemographicProfile]:
        """
        Generate n synthetic demographic profiles.

        Parameters
        ----------
        n            : Number of agents to generate
        h3_cells     : List of H3 cell indices for spatial placement
        cell_weights : Population weights for each cell (for realistic placement)
        """
        profiles = []
        for _ in range(n):
            nat = self._sample_nationality()
            age, gender = self.age_sex.sample_age_sex(self.rng)
            age = max(18, age)  # agents are adults

            occ = self._sample_occupation(nat)
            income = INCOME_BY_OCCUPATION.get(occ, "lower_middle")
            household = self._sample_household(age, nat)
            marital_status = self._sample_marital_status(household)
            num_children = self._sample_num_children(household)
            education = self._sample_education(age)
            years = self._sample_years_in_aoi(nat, age)

            # Spatial placement
            cell = None
            if h3_cells:
                weights = cell_weights or [1.0] * len(h3_cells)
                weights = np.array(weights) / sum(weights)
                cell = self.rng.choice(h3_cells, p=weights)

            profiles.append(DemographicProfile(
                agent_id=f"AGT-{uuid.uuid4().hex[:8].upper()}",
                age=int(age),
                gender=gender,
                nationality=nat,
                occupation=occ,
                income_bracket=income,
                household_type=household,
                marital_status=marital_status,
                num_children=num_children,
                h3_cell=cell,
                years_in_aoi=round(years, 1),
                education_level=education,
            ))

        return profiles
