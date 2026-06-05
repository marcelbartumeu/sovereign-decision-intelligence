"""
End-to-end pipeline demo for Andorra.

Runs the full data ingestion → H3 spatial layer → world context composition
→ population synthesis flow and prints a structured report.

Does NOT call the LLM — it produces the WorldContext and DemographicProfiles
that would be passed to the preference generation experiments.

Usage:
    cd research/pipeline
    pip install -r requirements.txt
    python demo_andorra.py [--no-api]   # --no-api skips live OSM/WorldBank calls

Output:
    - Prints world context that would be cached in the LLM system prompt
    - Prints 5 sample demographic profiles ready for LLM injection
    - Saves full output to ../pipeline_output/andorra_context.txt
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

# Allow imports from research/ root
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.aoi import andorra_aoi
from pipeline.ingest.worldpop import WorldPopClient, _wpp2022_age_sex
from pipeline.ingest.worldbank import get_profile, ANDORRA_FALLBACK
from pipeline.ingest.osm import OSMClient
from pipeline.context.composer import (
    WorldContextComposer,
    build_physical_layer_text,
    build_demographic_layer_text,
    build_institutional_layer_text,
    build_cultural_layer_text,
    build_situational_layer_text,
)
from pipeline.population.synthesizer import (
    PopulationSynthesizer,
    ANDORRA_NATIONALITY_DIST,
)

OUTPUT_DIR = Path(__file__).parent.parent / "pipeline_output"


def run(use_api: bool = True):
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("\n=== ANDORRA PIPELINE DEMO ===\n")

    # ── 1. AOI definition ──────────────────────────────────────────────────────
    print("Step 1: Define AOI and generate H3 grid (resolution 8)...")
    aoi = andorra_aoi(resolution=8)

    try:
        cells = aoi.h3_cells()
        print(f"         H3 cells generated: {len(cells)}")
    except ImportError:
        print("         h3 not installed — skipping cell generation (pip install h3)")
        cells = []

    # ── 2. WorldPop demographic layer ──────────────────────────────────────────
    print("Step 2: Fetch WorldPop age/sex structure...")
    age_sex = _wpp2022_age_sex("AND")
    print("         Using UN WPP 2022 age/sex structure for Andorra")

    nationality_mix = {
        "Andorran":   35.6,
        "Spanish":    33.5,
        "Portuguese": 17.1,
        "French":      6.6,
        "Other":       7.2,
    }

    demographic_text = build_demographic_layer_text(
        age_sex_structure=age_sex,
        nationality_mix=nationality_mix,
        total_population=90000,
    )

    # ── 3. OSM physical layer ──────────────────────────────────────────────────
    physical_text = ""
    if use_api:
        print("Step 3: Fetching OSM physical layer (Overpass API)...")
        try:
            osm = OSMClient(timeout=60)
            physical_layer = osm.fetch(aoi.geojson)
            summary = physical_layer.summary()
            print(f"         Features fetched: {sum(summary.values())} ({summary})")
            physical_text = build_physical_layer_text(physical_layer)
        except Exception as exc:
            print(f"         OSM fetch failed ({exc}) — using descriptive fallback")
            physical_text = _andorra_physical_fallback()
    else:
        print("Step 3: Using embedded physical layer description (--no-api mode)...")
        physical_text = _andorra_physical_fallback()

    # ── 4. World Bank institutional layer ─────────────────────────────────────
    print("Step 4: Loading World Bank institutional indicators...")
    if use_api:
        try:
            wb_profile = get_profile("AND", use_api=True)
        except Exception:
            wb_profile = ANDORRA_FALLBACK
    else:
        wb_profile = ANDORRA_FALLBACK

    institutional_text = build_institutional_layer_text(wb_profile)
    print(f"         {wb_profile.governance_summary()}")

    # ── 5. Cultural layer ──────────────────────────────────────────────────────
    print("Step 5: Composing cultural layer...")
    # Andorra sits in Secular-rational × Self-expression quadrant (EVS/WVS)
    # Coordinates approximate, interpolated from Spain (0.82, 0.71) and France (1.12, 0.89)
    cultural_text = build_cultural_layer_text(
        inglehart_welzel=(0.95, 0.78),
        wvs_trust=0.44,  # WVS Wave 7 Southern Europe average (Andorra uses Spain/France proxy)
        notes=(
            "Cultural notes specific to Andorra:\n"
            "  - Catalan is the official language; Spanish and French are widely spoken.\n"
            "  - Strong attachment to local parish identity (comú governance structure).\n"
            "  - Historical neutrality and co-principality creates pragmatic, consensus-oriented\n"
            "    political culture — low polarisation by European standards.\n"
            "  - Immigrant communities (esp. Portuguese) maintain strong origin-country cultural\n"
            "    values for 5–8 years before gradual acculturation (Berry 1997 framework).\n"
            "  - Tax haven reputation shapes attitudes to wealth, privacy, and state redistribution."
        )
    )

    # ── 6. Situational layer ───────────────────────────────────────────────────
    print("Step 6: Composing situational layer...")
    situational_text = build_situational_layer_text(
        current_stresses=[
            "Housing affordability crisis: rents consuming 50–70% of net income for working-class immigrants (CASS 2022)",
            "Tourism saturation: ~100 visitors/resident ratio generating quality-of-life backlash",
            "Climate risk to ski economy: IPCC AR6 projects Pyrenean snowline rising 200–400m by 2050",
            "Demographic dependency: structural reliance on immigrant labour with no citizenship pathway below 20-year threshold",
            "Cross-border labour competition: eroding wage premium relative to Barcelona/Toulouse",
        ],
        active_policies=[
            "Housing regulation debate: proposed rent caps and social housing expansion (parliamentary 2025)",
            "Tourism volume management: environmental impact assessment for peak-season caps",
            "Labour law reform: improving protections for temporary and seasonal workers",
            "Climate adaptation strategy: investment in non-ski tourism diversification",
            "EU alignment process: partial convergence with EU regulatory standards (ongoing)",
        ]
    )

    # ── 7. Compose world context ───────────────────────────────────────────────
    print("Step 7: Composing final world context...")
    context = (
        WorldContextComposer("Andorra", "AND", metadata=aoi.metadata)
        .add_physical_layer(physical_text)
        .add_demographic_layer(demographic_text)
        .add_institutional_layer(institutional_text)
        .add_cultural_layer(cultural_text)
        .add_situational_layer(situational_text)
        .build()
    )

    world_context_prompt = context.to_prompt()
    token_estimate = len(world_context_prompt.split()) * 1.3  # rough token estimate
    print(f"         World context length: {len(world_context_prompt)} chars (~{token_estimate:.0f} tokens)")

    # ── 8. Synthetic population sample ────────────────────────────────────────
    print("Step 8: Generating 10 synthetic demographic profiles...")
    synthesiser = PopulationSynthesizer(
        nationality_dist=ANDORRA_NATIONALITY_DIST,
        age_sex_structure=age_sex,
    )
    sample_profiles = synthesiser.generate(n=10)

    # ── Output ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("WORLD CONTEXT PROMPT (to be cached in LLM system prompt):")
    print("=" * 60)
    print(world_context_prompt)

    print("\n" + "=" * 60)
    print("SAMPLE DEMOGRAPHIC PROFILES (LLM input for preference generation):")
    print("=" * 60)
    for p in sample_profiles[:5]:
        print(f"  {p.agent_id}: {p.to_prompt_string()}")

    # Save outputs
    context_path = OUTPUT_DIR / "andorra_world_context.txt"
    profiles_path = OUTPUT_DIR / "andorra_sample_profiles.json"

    context_path.write_text(world_context_prompt)
    with open(profiles_path, "w") as f:
        json.dump([p.__dict__ for p in sample_profiles], f, indent=2)

    print(f"\nOutputs saved to {OUTPUT_DIR}/")
    print(f"  World context: {context_path.name} ({context_path.stat().st_size} bytes)")
    print(f"  Sample profiles: {profiles_path.name}")

    return context, sample_profiles


def _andorra_physical_fallback() -> str:
    """Embedded physical layer description when Overpass API is unavailable."""
    return """Physical infrastructure of Andorra (OpenStreetMap, 2024 extract):

  Healthcare facilities (hospitals, clinics, pharmacies): ~45 nodes
    - Primary: Hospital Nostra Senyora de Meritxell (Escaldes-Engordany, 244 beds)
    - 6 primary care centres distributed across parishes
    - ~35 pharmacies, predominantly in urban core

  Educational institutions (schools, universities, libraries): ~60 nodes
    - 3 school systems: Andorran, Spanish (concerted), French (laïque)
    - University of Andorra (UdA): main campus Andorra la Vella
    - ~30 primary/secondary schools across all parishes

  Commercial nodes (supermarkets, retail, banks): ~380 nodes
    - High retail density in Andorra la Vella and Escaldes (duty-free zone)
    - Major supermarkets: Bon Preu, Punt de Trobada, La Morera
    - ~25 bank branches (including offshore/private banking sector)

  Public transit stops (bus, inter-urban): ~85 nodes
    - Bus Públic d'Andorra (BPA): urban routes + inter-parish routes
    - No rail network; road-dependent mobility
    - International connections: regular coaches to Barcelona, Toulouse, Madrid

  Leisure & hospitality venues: ~650 nodes
    - Ski areas: Grandvalira (210 km pistes), Vallnord (93 km pistes), Ordino-Arcalís
    - ~400 restaurants/bars concentrated in urban core and resort villages
    - ~120 hotels ranging from budget to 5-star

  Civic facilities (town halls, police, post): ~40 nodes
    - Comú (local council) per parish: 7 comuns total
    - Policia d'Andorra: national force + local batllia courts
    - Nota: no military — permanent demilitarisation by treaty

  Mobility context:
    High car dependency (no rail, mountain terrain, dispersed parishes).
    Transit willingness structurally limited by geography.
    Cross-border mobility (to Spain/France) common for shopping, healthcare, work."""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-api", action="store_true",
                        help="Skip live API calls (OSM, WorldBank); use embedded data")
    args = parser.parse_args()
    run(use_api=not args.no_api)
