"""
Preference profile schema grounded in validated psychometric frameworks.

Personality  → Big Five (Costa & McCrae 1992), the cross-cultural gold standard.
               Scores normalised to [0,1] from standard T-scores (mean=50, sd=10).
Values       → Schwartz Basic Human Values (Schwartz 1992), validated in 80+ countries.
               Top-3 priority ranking captures motivational hierarchy.
Political    → Two-dimensional model (economic × social), standard in political science.
               Anchored to Chapel Hill Expert Survey / Manifesto Project coding.
Behavioral   → Prospect Theory loss-aversion λ (Kahneman & Tversky 1979).
               β-δ quasi-hyperbolic discounting (Laibson 1997).
Trust        → World Values Survey trust battery (Inglehart et al., WVS Wave 7).
Social cap.  → Putnam (2000) bonding/bridging capital distinction.
"""

import numpy as np

OUTPUT_SCHEMA = """
{
  "summary": "One sentence capturing this person's character and lived situation in the AOI.",

  "personality": {
    // Big Five (OCEAN) — normalised 0-1 from population T-score distributions
    // Population means cluster near 0.50; SD ≈ 0.10–0.15
    "openness":          0.0-1.0,   // curiosity, creativity, tolerance of novelty
    "conscientiousness": 0.0-1.0,   // self-discipline, planning, rule-following
    "extraversion":      0.0-1.0,   // sociability, assertiveness, positive affect
    "agreeableness":     0.0-1.0,   // cooperativeness, trust of others, empathy
    "neuroticism":       0.0-1.0    // anxiety, stress-reactivity, emotional instability
  },

  "schwartz_values": {
    // Top-3 from the 10 Schwartz motivational value types (rank order matters)
    // Valid options: security, conformity, tradition, benevolence, universalism,
    //               self_direction, achievement, power, hedonism, stimulation
    "primary":   "string",
    "secondary": "string",
    "tertiary":  "string"
  },

  "political": {
    // Two-dimensional positioning (political science standard)
    "economic_axis": 0.0-1.0,  // 0=fully redistributive/state-led, 1=fully market/liberal
    "social_axis":   0.0-1.0,  // 0=authoritarian/communitarian, 1=libertarian/individualist
    "local_engagement": 0.0-1.0,
    "institutional_trust": {
      // Anchored to WVS trust battery question wording
      "government":    0.0-1.0,  // "How much confidence do you have in the government?"
      "legal_system":  0.0-1.0,  // "...the justice system?"
      "employers":     0.0-1.0,
      "media":         0.0-1.0,
      "interpersonal": 0.0-1.0   // "Most people can be trusted" (0=No, 1=Yes)
    },
    "issue_salience": {
      // How much does each issue personally matter? (0=irrelevant, 1=top concern)
      "housing":      0.0-1.0,
      "environment":  0.0-1.0,
      "immigration":  0.0-1.0,
      "economy":      0.0-1.0,
      "tourism":      0.0-1.0
    }
  },

  "behavioral_economics": {
    // Prospect Theory (Kahneman & Tversky 1979)
    "loss_aversion": 1.0-4.5,  // λ: losses feel λ× worse than equivalent gains
                                // Population mean ≈ 2.25; high stress → higher λ
    // β-δ quasi-hyperbolic discounting (Laibson 1997)
    "discount_rate":  0.03-0.35, // δ: annual patience rate (0.03=very patient, 0.25=impulsive)
    "present_bias":   0.50-1.00  // β: extra present-moment bias (1.0=time-consistent)
  },

  "mobility": {
    "primary_mode":          "car | walk | transit | bike | mixed",
    "transit_willingness":   0.0-1.0,
    "walking_radius_km":     0.5-5.0,
    "cross_border_frequency":"daily | weekly | monthly | rarely | never",
    "car_dependent":         true | false
  },

  "economic": {
    // Subjective measures (perceived, not objective income)
    "financial_stress":            0.0-1.0,  // "Difficulty making ends meet"
    "savings_orientation":         0.0-1.0,
    "price_sensitivity":           0.0-1.0,
    "employment_security_perception": 0.0-1.0
  },

  "social": {
    "bonding_capital":    0.0-1.0,  // Putnam: strength of ties to similar others (family, ethnic)
    "bridging_capital":   0.0-1.0,  // Putnam: ties across groups (neighbours, colleagues)
    "civic_participation":0.0-1.0,  // voluntary associations, community groups
    "network_density":    "sparse | moderate | dense"
  },

  "employment_status": "string",
  // One of: employed_full_time | employed_part_time | self_employed |
  //         unemployed | retired | student | homemaker
  // Must be consistent with income_bracket and age provided in the prompt.
  // Rationale: narratively grounds the agent's daily schedule structure.

  "household_composition": "string",
  // One of: single | couple_no_children | couple_with_children |
  //         single_parent | multi_generational | shared_accommodation
  // Must reflect realistic housing patterns for the agent's nationality,
  // income, and age in Andorra.

  "goals": {
    "short_term":  ["string", "string"],  // 1–2 year horizon
    "long_term":   ["string", "string"],  // 5–10 year horizon
    "primary_fear":"string"               // single most salient threat to their life plan
  },

  "place_preferences": {
    // Weekly likelihood of visiting each destination type: float in [0.01, 0.99].
    // Baselines are Eurostat population averages for Andorra (HETUS/Eurobarometer/EHIS/Pew).
    // Reason from this agent's full profile — adjust each baseline up or down
    // based on their personality, values, age, income, employment, and household.
    //
    // Hard demographic rules — you MUST follow these:
    //   D8 + D17 (healthcare/pharmacy): increase sharply with age; agents 65+ should be 2–3× baseline
    //   D7  (religious):  tradition or conformity values → higher; secular agents → near-zero
    //   D23 (bar):        youth (18–35) only; agents over 55 should be near 0.02–0.05
    //   D5  (education):  students and youth only; near-zero for retired agents
    //   D13 (executive housing): only above 0.25 for wealthy or comfortable income
    //   D12 (affordable housing): only above 0.30 for precarious or low income
    //   D11 (senior housing): only above 0.20 for agents aged 60+
    //   D19 (daycare): only above 0.15 for agents with couple_with_children or single_parent household
    //   D27 (mountain/outdoor): Andorra-specific; baseline is already higher than W. European average
    //   D15 (grocery): near-universal — keep close to baseline unless very unusual profile
    //
    "D3":  0.01-0.99,  // Retail Store          [baseline 0.52]  income↑ price_sensitivity↓
    "D4":  0.01-0.99,  // Commercial/Work zone  [baseline 0.55]  employed adults; employment_security↑
    "D5":  0.01-0.99,  // Education             [baseline 0.22]  students and youth; near-zero retired
    "D6":  0.01-0.99,  // General Housing       [baseline 0.50]  housing issue salience; financial_stress↑
    "D7":  0.01-0.99,  // Religious             [baseline 0.12]  tradition/conformity values; age↑
    "D8":  0.01-0.99,  // Healthcare            [baseline 0.09]  age↑ neuroticism↑ financial_stress↑
    "D9":  0.01-0.99,  // Government/Civic      [baseline 0.06]  civic_participation↑ local_engagement↑
    "D10": 0.01-0.99,  // Mid-Career Housing    [baseline 0.42]  working-age middle income
    "D11": 0.01-0.99,  // Senior Housing        [baseline 0.11]  age 60+ only
    "D12": 0.01-0.99,  // Affordable Housing    [baseline 0.38]  precarious/low income; financial_stress↑
    "D13": 0.01-0.99,  // Executive Housing     [baseline 0.11]  wealthy/comfortable only
    "D14": 0.01-0.99,  // Headquarter Office    [baseline 0.38]  professional/managerial workers
    "D15": 0.01-0.99,  // Grocery Market        [baseline 0.85]  near-universal; price_sensitivity mild↑
    "D16": 0.01-0.99,  // Recreation/Fitness    [baseline 0.38]  active adults; declines sharply 65+
    "D17": 0.01-0.99,  // Pharmacy              [baseline 0.12]  age↑ neuroticism↑
    "D18": 0.01-0.99,  // Career Training       [baseline 0.08]  youth; achievement/self_direction values
    "D19": 0.01-0.99,  // Daycare               [baseline 0.14]  parents with young children only
    "D20": 0.01-0.99,  // Coworking Office      [baseline 0.22]  self_employed; bridging_capital↑
    "D21": 0.01-0.99,  // Restaurant            [baseline 0.38]  income↑ hedonism/stimulation values
    "D22": 0.01-0.99,  // Café                  [baseline 0.42]  broad appeal; bridging_capital↑ openness↑
    "D23": 0.01-0.99,  // Bar                   [baseline 0.20]  youth only; near-zero 55+
    "D24": 0.01-0.99,  // Pub                   [baseline 0.22]  bonding_capital↑; broader age than bar
    "D25": 0.01-0.99,  // Park                  [baseline 0.48]  environment salience↑ walking_radius↑
    "D26": 0.01-0.99,  // Cultural Venue        [baseline 0.12]  openness↑ income↑ achievement values
    "D27": 0.01-0.99,  // Mountain/Outdoor      [baseline 0.30]  Andorra-specific; active youth/adults
    "D28": 0.01-0.99   // Personal Services     [baseline 0.22]  working-age; conscientiousness↑
  }
}
"""

# Numerical fields extracted for metric computation
# Format: (path_tuple, label)
NUMERICAL_FIELDS = [
    (("personality", "openness"),                             "big5.O"),
    (("personality", "conscientiousness"),                    "big5.C"),
    (("personality", "extraversion"),                         "big5.E"),
    (("personality", "agreeableness"),                        "big5.A"),
    (("personality", "neuroticism"),                          "big5.N"),
    (("political", "economic_axis"),                          "pol.economic"),
    (("political", "social_axis"),                            "pol.social"),
    (("political", "local_engagement"),                       "pol.engagement"),
    (("political", "institutional_trust", "government"),      "trust.govt"),
    (("political", "institutional_trust", "legal_system"),    "trust.legal"),
    (("political", "institutional_trust", "interpersonal"),   "trust.people"),
    (("behavioral_economics", "loss_aversion"),               "be.loss_aversion"),
    (("behavioral_economics", "discount_rate"),               "be.discount_rate"),
    (("behavioral_economics", "present_bias"),                "be.present_bias"),
    (("mobility", "transit_willingness"),                     "mob.transit"),
    (("economic", "financial_stress"),                        "econ.stress"),
    (("economic", "savings_orientation"),                     "econ.savings"),
    (("economic", "price_sensitivity"),                       "econ.price_sens"),
    (("social", "bonding_capital"),                           "social.bonding"),
    (("social", "bridging_capital"),                          "social.bridging"),
    (("social", "civic_participation"),                       "social.civic"),
]

FIELD_LABELS = [label for _, label in NUMERICAL_FIELDS]


def _get_nested(d: dict, path: tuple):
    for key in path:
        d = d[key]
    return d


def profile_to_vector(profile: dict) -> np.ndarray:
    vals = []
    for path, _ in NUMERICAL_FIELDS:
        try:
            v = float(_get_nested(profile, path))
            # Normalise loss_aversion and discount_rate to [0,1] for metric computation
            if path == ("behavioral_economics", "loss_aversion"):
                v = (v - 1.0) / 3.5  # maps [1.0, 4.5] → [0, 1]
            elif path == ("behavioral_economics", "discount_rate"):
                v = (v - 0.03) / 0.32  # maps [0.03, 0.35] → [0, 1]
        except (KeyError, TypeError, ValueError):
            v = 0.5  # fallback for missing fields
        vals.append(v)
    return np.array(vals)


def parse_llm_json(text: str) -> dict:
    import json
    import re
    text = text.strip()
    # Strip markdown fences
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else parts[0]
        if text.startswith("json"):
            text = text[4:]
    # Strip inline comments (// ...) before JSON parsing
    text = re.sub(r"//[^\n]*", "", text)
    return json.loads(text.strip())
