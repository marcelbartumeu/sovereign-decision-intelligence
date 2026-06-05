"""
Andorra knowledge graph.

Encodes the sociological branch constraints from exp02_hag as graph edges.
Same knowledge — different representation. The if-else tree is gone; adding
a new constraint is now adding one Edge rather than editing nested conditions.

To build a graph for a different country: copy this file, replace the nodes
and edges with that country's sociological data, and point ACTIVE_GRAPH at it.

Future: auto-generate this file via GraphRAG ingestion from:
  - SAIG Anuari Estadístic (census, labour, housing)
  - CASS wage and income reports
  - IMF Article IV consultation
  - Policy documents (housing law, immigration rules)
  - News corpus (structural stresses, current events)

Sources for current values
──────────────────────────
Nationality constraints  : SAIG 2023; Vallès (2022) on Andorran social stratification
Income constraints       : CASS 2022 labour report; ILO informal work thresholds
Age constraints          : Big Five age norms (Roberts et al. 2006); WVS age × trust
Occupation constraints   : Ministerio de Treball i Afers Socials d'Andorra 2023
Context nodes            : IMF 2024 Article IV; SAIG housing price index 2023
"""

from .knowledge_graph import KnowledgeGraph, Node, Edge, FieldConstraint


def build_andorra_graph() -> KnowledgeGraph:
    g = KnowledgeGraph()

    # ── Nodes ─────────────────────────────────────────────────────────────────

    # Nationality
    g.add_node(Node("nat:Andorran",   "demographic", "Andorran national"))
    g.add_node(Node("nat:Spanish",    "demographic", "Spanish resident"))
    g.add_node(Node("nat:Portuguese", "demographic", "Portuguese immigrant"))
    g.add_node(Node("nat:French",     "demographic", "French expat"))
    g.add_node(Node("nat:Other",      "demographic", "non-EU immigrant"))

    # Residence duration
    g.add_node(Node("years:recent",      "demographic", "recent arrival (<5 yrs)"))
    g.add_node(Node("years:settling",    "demographic", "settling in (5–10 yrs)"))
    g.add_node(Node("years:established", "demographic", "established resident (10+ yrs)"))

    # Age groups
    g.add_node(Node("age:young_adult",    "demographic", "young adult (15–26)"))
    g.add_node(Node("age:prime",          "demographic", "prime working age (27–41)"))
    g.add_node(Node("age:established",    "demographic", "established adult (42–57)"))
    g.add_node(Node("age:pre_retirement", "demographic", "pre-retirement / retired (58+)"))

    # Income brackets
    g.add_node(Node("income:precarious",   "demographic", "precarious income"))
    g.add_node(Node("income:low",          "demographic", "low income"))
    g.add_node(Node("income:lower_middle", "demographic", "lower-middle income"))
    g.add_node(Node("income:middle",       "demographic", "middle income"))
    g.add_node(Node("income:upper_middle", "demographic", "upper-middle income"))
    g.add_node(Node("income:comfortable",  "demographic", "comfortable income"))
    g.add_node(Node("income:wealthy",      "demographic", "wealthy"))

    # Occupations
    g.add_node(Node("occ:cross_border_worker", "demographic", "Spanish cross-border commuter"))
    g.add_node(Node("occ:business_owner",      "demographic", "business owner"))

    # Situational context — always active; represent persistent structural facts
    g.add_node(Node("ctx:housing_crisis",    "context", "housing affordability crisis"))
    g.add_node(Node("ctx:tourism_pressure",  "context", "high tourism pressure"))
    g.add_node(Node("ctx:tight_labour",      "context", "near-zero unemployment, labour scarcity"))

    # ── Nationality edges ─────────────────────────────────────────────────────

    g.add_edge(Edge(
        ["nat:Andorran"],
        [
            FieldConstraint("bonding_capital",             0.60, 0.90, note="rooted in the territory"),
            FieldConstraint("political.institutional_trust.government", 0.40, 0.72),
            FieldConstraint("political.local_engagement",  0.45, 0.80),
        ],
        note="Andorran nationals — high territorial attachment",
        narrative=(
            "Andorran nationals are a minority in their own country (roughly 33% of residents) "
            "and carry a strong sense of territorial identity tied to language, parish governance, "
            "and land ownership traditions. They navigate a paradox: benefiting economically from "
            "tourism and cross-border commerce while feeling pressure on cultural continuity. "
            "Institutional trust is moderate — the small size of government makes it personally "
            "legible, but also susceptible to perceived patronage. Local political engagement is "
            "high; parish council decisions feel directly consequential."
        ),
    ))

    g.add_edge(Edge(
        ["nat:Portuguese"],
        [
            FieldConstraint("political.institutional_trust.government", 0.20, 0.50,
                            note="trust in institutions: low-to-moderate"),
            FieldConstraint("economic.price_sensitivity", 0.60, 0.90,
                            note="housing affordability concern: very high"),
        ],
        note="Portuguese immigrants — baseline constraints",
        narrative=(
            "Portuguese immigrants form the largest non-national group (~26% of residents). "
            "Most arrived in construction, hospitality, and domestic service — sectors with "
            "high turnover and informal employment. Housing is the dominant economic pressure: "
            "rents averaging €2,400/month consume a disproportionate share of Portuguese wages. "
            "Remittances to Portugal add a further financial strain for those with family abroad. "
            "Trust in Andorran institutions is cautious — shaped by experiences of bureaucratic "
            "opacity in residency and work permit processes."
        ),
    ))

    g.add_edge(Edge(
        ["nat:Portuguese", "years:recent"],
        [
            FieldConstraint("economic.financial_stress",  0.65, 0.90, priority=2,
                            note="legal status uncertainty creates background stress"),
            FieldConstraint("social.bonding_capital",     0.25, 0.45, priority=2,
                            note="still building roots"),
        ],
        note="Portuguese recent arrivals — elevated precarity",
        narrative=(
            "A Portuguese person who arrived less than five years ago is still in the most "
            "financially exposed phase of immigrant life in Andorra. Without established "
            "residency status, access to subsidised housing or CASS healthcare is limited. "
            "Their social network is thin — mostly recent compatriots in similar situations — "
            "and the language barrier (Catalan in official contexts, though Spanish works daily) "
            "adds friction. Financial stress is elevated by the combination of housing costs, "
            "legal fees, and the absence of a savings buffer built over time."
        ),
    ))

    g.add_edge(Edge(
        ["nat:Portuguese", "years:settling"],
        [
            FieldConstraint("economic.financial_stress", 0.50, 0.75, priority=1),
            FieldConstraint("social.bonding_capital",    0.40, 0.65, priority=1,
                            note="invested in staying"),
        ],
        note="Portuguese settling in",
        narrative=(
            "A Portuguese resident of 5–10 years is in a consolidation phase. Residency is "
            "more secure, and their professional network has deepened. Many have shifted from "
            "survival mode to medium-term planning — considering whether to stay permanently "
            "or eventually return to Portugal. Bonding capital is growing but remains tied "
            "mainly to the Portuguese community. Financial stress is easing but housing "
            "costs continue to absorb 40–55% of income for many in this group."
        ),
    ))

    g.add_edge(Edge(
        ["nat:Portuguese", "years:established"],
        [
            FieldConstraint("economic.financial_stress", 0.35, 0.65, priority=1),
            FieldConstraint("social.bonding_capital",    0.50, 0.75, priority=1),
        ],
        note="Portuguese established residents",
        narrative=(
            "Established Portuguese residents (10+ years) often own or have long-term rental "
            "stability, have children in Andorran schools, and participate in parish activities. "
            "Many hold permanent residency and identify with Andorra as home, even while "
            "maintaining strong cultural ties to Portugal. Financial stress is moderate — "
            "accumulated savings and better employment positions provide some buffer, though "
            "the structural cost of living remains high."
        ),
    ))

    g.add_edge(Edge(
        ["nat:Spanish"],
        [
            FieldConstraint("economic.financial_stress",  0.35, 0.65),
            FieldConstraint("social.bonding_capital",     0.40, 0.65,
                            note="culturally proximate to Andorra"),
            FieldConstraint("political.institutional_trust.government", 0.35, 0.60),
        ],
        note="Spanish residents — baseline",
        narrative=(
            "Spanish residents in Andorra (~21% of residents) span two distinct groups: "
            "long-term immigrants who live and work there full-time, and cross-border workers "
            "who commute daily from towns like La Seu d'Urgell. Cultural and linguistic "
            "proximity to Andorra (Catalan is shared) eases integration compared to other "
            "immigrant groups. Many Spanish residents have been in Andorra for decades and "
            "are well-embedded in local commerce and professional life."
        ),
    ))

    g.add_edge(Edge(
        ["nat:Spanish", "occ:cross_border_worker"],
        [
            FieldConstraint("social.bonding_capital",       0.20, 0.40, priority=2,
                            note="primary life is in Spain"),
            FieldConstraint("mobility.transit_willingness", 0.65, 0.95, priority=2,
                            note="commuting is the daily reality"),
            FieldConstraint("political.local_engagement",   0.02, 0.20, priority=2),
        ],
        note="Spanish cross-border commuters",
        narrative=(
            "Spanish cross-border workers (frontalers) commute daily through the mountain "
            "passes from the Alt Urgell and Pallars Sobirà. They spend their earning hours in "
            "Andorra but their social, family, and civic lives remain in Spain. They benefit "
            "from Andorra's low taxes and wages without paying into Andorran social infrastructure "
            "to the same degree as residents. Their investment in Andorran community outcomes is "
            "minimal — they have no political stake, no housing costs in Andorra, and social "
            "ties that exist almost entirely across the border."
        ),
    ))

    g.add_edge(Edge(
        ["nat:French"],
        [
            FieldConstraint("economic.financial_stress",    0.15, 0.45,
                            note="typically professional income"),
            FieldConstraint("political.local_engagement",   0.05, 0.30,
                            note="not deeply invested in Andorran politics"),
            FieldConstraint("economic.savings_orientation", 0.45, 0.75),
        ],
        note="French professional expats",
        narrative=(
            "French residents in Andorra (~6% of the population) are disproportionately "
            "professionals — managers, business owners, and finance workers attracted by "
            "the tax regime. Many are lifestyle migrants who chose Andorra for its mountain "
            "environment and quality of life. Their financial stress is low compared to other "
            "immigrant groups, and they tend toward higher savings orientation given the "
            "tax advantages. Political engagement with Andorran institutions is minimal; "
            "they follow French political news more closely than Andorran parish politics."
        ),
    ))

    g.add_edge(Edge(
        ["nat:Other"],
        [
            FieldConstraint("economic.financial_stress",    0.60, 0.90,
                            note="most non-EU workers face precarity"),
            FieldConstraint("political.institutional_trust.government", 0.10, 0.35,
                            note="limited legal protections"),
            FieldConstraint("social.bonding_capital",       0.15, 0.45,
                            note="often isolated from mainstream society"),
        ],
        note="Non-EU immigrants",
        narrative=(
            "Non-EU immigrants in Andorra (~14% of residents, including Moroccans, Colombians, "
            "and others) occupy the most precarious position in the social structure. Work "
            "permits are tied to specific employers, limiting job mobility. Many work in "
            "hospitality, cleaning, and construction under informal or short-term contracts. "
            "Housing options are severely constrained — they often share overcrowded flats "
            "due to rental market exclusion. Trust in government institutions is low, shaped "
            "by vulnerability to deportation and the absence of a clear path to permanent "
            "residency. Social networks are tight within their own community but weakly "
            "connected to broader Andorran society."
        ),
    ))

    # ── Income edges ──────────────────────────────────────────────────────────

    _income_ranges = {
        "precarious":   (0.65, 0.92, 0.02, 0.12, 0.80, 0.98),
        "low":          (0.55, 0.80, 0.05, 0.18, 0.70, 0.90),
        "lower_middle": (0.48, 0.72, 0.08, 0.22, 0.60, 0.82),
        "middle":       (0.30, 0.58, 0.18, 0.38, 0.40, 0.65),
        "upper_middle": (0.18, 0.42, 0.32, 0.55, 0.25, 0.50),
        "comfortable":  (0.10, 0.32, 0.45, 0.70, 0.15, 0.38),
        "wealthy":      (0.03, 0.18, 0.65, 0.90, 0.05, 0.22),
    }
    _income_narratives = {
        "precarious": (
            "At this income level (below €1,300/month) in Andorra, a person is operating "
            "at or below the minimum wage in one of Europe's most expensive microstates. "
            "A single room in shared housing can consume 60–80% of income. Savings are "
            "structurally impossible. Every unexpected expense — a health issue, a car repair, "
            "a travel home — requires debt or assistance from family. Financial decisions are "
            "dominated by immediate survival rather than planning. Loss aversion is acute "
            "because there is no buffer to absorb any loss."
        ),
        "low": (
            "Earning €1,300–1,700/month in Andorra means covering basic needs but with "
            "very little slack. Shared housing is the norm. Discretionary spending is "
            "tightly managed. This income bracket often corresponds to service and "
            "hospitality workers — jobs with uncertain hours and limited advancement. "
            "A small but meaningful savings capacity exists in good months, but it "
            "evaporates quickly when housing costs rise or hours fall."
        ),
        "lower_middle": (
            "€1,700–2,200/month places someone slightly above survival but well below "
            "comfort in Andorra's cost structure. This person can pay rent on a modest "
            "flat (possibly shared), cover food and transport, and save a modest amount. "
            "Price sensitivity remains high — they notice and respond to price changes "
            "in groceries, fuel, and services. Financial planning is short-horizon; "
            "medium-term goals (buying property, higher education) feel distant."
        ),
        "middle": (
            "At €2,200–3,000/month, a person in Andorra can live independently and "
            "maintain some financial resilience. Housing is affordable as a single occupant "
            "in a modest flat. Savings accumulation is feasible. This is the income range "
            "where consumer choice expands and lifestyle spending becomes possible. "
            "Financial stress exists but is manageable — disruptions are unpleasant "
            "rather than existential. Price sensitivity is moderate; quality matters "
            "alongside price."
        ),
        "upper_middle": (
            "€3,000–4,500/month in Andorra represents genuine financial comfort. "
            "Housing costs are a manageable fraction of income. Savings and investment "
            "are active practices. This income level typically reflects professional "
            "roles, management, or skilled trades. Loss aversion shifts from survival-"
            "oriented to wealth-preservation-oriented. Longer planning horizons are "
            "possible — pension, property, education for children."
        ),
        "comfortable": (
            "€4,500–7,000/month puts a person in Andorra's upper-middle professional "
            "class. Andorra's low tax environment is now a meaningful financial advantage "
            "rather than an abstraction. Savings orientation is strong and conscious. "
            "Financial stress is low and largely decoupled from day-to-day costs. "
            "Risk tolerance may be moderate-to-high in investment contexts. "
            "Decisions are driven by optimisation rather than necessity."
        ),
        "wealthy": (
            "Above €7,000/month, an Andorran resident is benefiting substantially from "
            "the principality's tax regime relative to neighbouring France and Spain. "
            "Many in this bracket are business owners, senior managers, or individuals "
            "who relocated specifically for fiscal reasons. Financial stress is negligible. "
            "Savings orientation is high but aimed at wealth growth rather than security. "
            "Price sensitivity is low. Decision-making emphasises long-term positioning, "
            "asset allocation, and cross-border financial planning."
        ),
    }
    for bracket, (fs_lo, fs_hi, sv_lo, sv_hi, ps_lo, ps_hi) in _income_ranges.items():
        g.add_edge(Edge(
            [f"income:{bracket}"],
            [
                FieldConstraint("economic.financial_stress",    fs_lo, fs_hi),
                FieldConstraint("economic.savings_orientation", sv_lo, sv_hi),
                FieldConstraint("economic.price_sensitivity",   ps_lo, ps_hi),
            ],
            note=f"{bracket} income bracket",
            narrative=_income_narratives[bracket],
        ))

    # ── Age edges ─────────────────────────────────────────────────────────────

    g.add_edge(Edge(
        ["age:young_adult"],
        [
            FieldConstraint("personality.openness",              0.48, 0.78,
                            note="higher tolerance for novelty and risk"),
            FieldConstraint("behavioral_economics.present_bias", 0.70, 0.95,
                            note="stronger present-moment discounting"),
            FieldConstraint("behavioral_economics.discount_rate",0.12, 0.30,
                            note="less patient on average"),
        ],
        narrative=(
            "Young adults in Andorra (15–26) are navigating a bifurcated reality: those from "
            "wealthier families live comfortably in a mountain playground with excellent skiing "
            "and low taxes; those from immigrant families may already be working full-time in "
            "hospitality or retail. Both groups share high openness to experience and a "
            "present-biased temporal horizon — long-term saving and planning feel abstract. "
            "In Andorra's tight labour market, youth unemployment is very low, which reduces "
            "anxiety about immediate employment but doesn't address the structural issue that "
            "property ownership is essentially out of reach."
        ),
    ))

    g.add_edge(Edge(
        ["age:prime"],
        [
            FieldConstraint("personality.openness",  0.35, 0.65),
            FieldConstraint("behavioral_economics.discount_rate", 0.06, 0.20),
        ],
        narrative=(
            "Prime working-age adults (27–41) in Andorra are in the peak household-formation "
            "phase — but Andorra's housing market makes this extraordinarily difficult. "
            "Rental prices and property values have risen 40%+ since 2018. Many in this group "
            "are making active decisions about whether to stay in Andorra long-term or relocate "
            "to Spain or Portugal where housing is more accessible. Those who stay often do so "
            "for career reasons or family ties. Openness to experience is moderate; planning "
            "horizons are medium-term and focused on financial consolidation."
        ),
    ))

    g.add_edge(Edge(
        ["age:established"],
        [
            FieldConstraint("personality.openness",  0.28, 0.58),
            FieldConstraint("behavioral_economics.discount_rate", 0.04, 0.15),
        ],
        narrative=(
            "Established adults (42–57) in Andorra are typically the most economically settled "
            "cohort. Many have built careers in the principality's dominant sectors — tourism, "
            "retail, construction, or business services — and have longer-term financial "
            "stability. Patience in financial decisions is higher; they are less present-biased. "
            "Openness is moderate. Those who own property are benefiting from price appreciation; "
            "those who don't are increasingly locked out and may be considering emigration. "
            "This age group carries the heaviest responsibility for dependent children and "
            "often ageing parents in their home countries."
        ),
    ))

    g.add_edge(Edge(
        ["age:pre_retirement"],
        [
            FieldConstraint("personality.openness",  0.20, 0.52),
            FieldConstraint("behavioral_economics.discount_rate", 0.03, 0.10,
                            note="more patient — retirement horizon"),
            FieldConstraint("social.bonding_capital", 0.55, 0.85,
                            note="invested in the place over decades"),
        ],
        narrative=(
            "Pre-retirement adults (58+) in Andorra have, by definition, survived the "
            "pressures that push many immigrants out in their 30s and 40s. Those who remain "
            "at this age are typically deeply embedded — they have built social networks, "
            "often own or have long-term housing, and identify strongly with the community. "
            "CASS pension calculations incentivise longer stay. Openness to change is lower; "
            "stability and continuity are the dominant values. Bonding capital is high. "
            "Planning is long-horizon, focused on retirement security and legacy."
        ),
    ))

    # ── Context edges — situational modifiers always active ───────────────────

    g.add_edge(Edge(
        ["ctx:housing_crisis"],
        [
            FieldConstraint("political.issue_salience.housing",  0.70, 0.98,
                            note="housing cost is the #1 concern across groups"),
            FieldConstraint("economic.financial_stress",         0.05, 0.15,
                            note="housing crisis adds baseline stress floor",
                            direction="high", priority=-1),  # additive, not range
        ],
        note="Ongoing housing affordability crisis (SAIG 2023: rent +40% in 5 years)",
        narrative=(
            "Andorra's housing crisis is the defining structural stress of the 2020s. "
            "Between 2018 and 2023, average rents increased over 40%, driven by a combination "
            "of remote-worker influx post-pandemic, speculative investment from neighbouring "
            "countries, and a legally constrained supply (protected mountain territory limits "
            "construction). The median rent for a two-bedroom flat now exceeds €2,000/month. "
            "For a country with a median salary of roughly €2,050/month, this means housing "
            "consumes the majority of most residents' income. The crisis cuts across nationalities "
            "but falls hardest on recent immigrants and young adults. Political salience is "
            "extremely high — it is discussed in every public forum and is the primary driver "
            "of discontent with government across all demographic groups."
        ),
    ))

    g.add_edge(Edge(
        ["ctx:tourism_pressure"],
        [
            FieldConstraint("political.issue_salience.tourism",  0.55, 0.90),
        ],
        note="11M+ tourists/year for 90k residents",
        narrative=(
            "Andorra receives over 11 million tourists annually for a resident population of "
            "roughly 90,000 — a ratio of 120:1. Tourism is the economic backbone, generating "
            "the tax revenue that funds public services and the commercial activity that employs "
            "a large share of the workforce. But it also distorts daily life: roads clog with "
            "day-trippers buying discounted tobacco and alcohol, service workers face gruelling "
            "seasonal peaks, and the character of parishes shifts around commercial strips. "
            "Attitudes toward tourism are ambivalent — economically necessary, socially taxing. "
            "Residents have strong opinions on how tourism should be managed and limited."
        ),
    ))

    g.add_edge(Edge(
        ["ctx:tight_labour", "nat:Andorran"],
        [
            FieldConstraint("economic.employment_security_perception", 0.65, 0.92,
                            note="Andorrans benefit most from tight labour market"),
        ],
        narrative=(
            "Andorra's unemployment rate is consistently below 2% — effectively zero by "
            "any practical measure. For Andorran nationals, this creates a strong sense of "
            "employment security: there is always work available, and employers compete for "
            "local talent. Andorrans tend to feel more confident about career mobility and "
            "less anxious about job loss than their counterparts in neighbouring countries. "
            "This security also shapes their negotiating posture with employers and their "
            "tolerance for risk in career decisions."
        ),
    ))

    return g


# Singleton — build once, reuse across all archetype generation calls
ANDORRA_GRAPH = build_andorra_graph()
