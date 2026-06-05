#!/usr/bin/env python3
"""
Update Front end/js/scenarioData.js from model output JSON files.
Run from Front end/model/ after CALCULATOR.py has generated *_final.json and *_timeseries.json.
Preserves current scenario and historicalSeries; replaces continuity, overgrowth, degrowth, density
and their timeseriesData from the JSON files.
"""
import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
JS_DIR = SCRIPT_DIR.parent / "js"
SCENARIO_DATA_JS = JS_DIR / "scenarioData.js"

SCENARIOS = ["Continuity", "Overgrowth", "Degrowth", "Density"]
SKIP_KEYS = {"HPrice_prev"}  # internal, do not expose in scenarioData


def js_value(v):
    """Format a Python value as JavaScript literal."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        if isinstance(v, int):
            return str(v)
        s = repr(v)
        # avoid trailing zeros for floats when possible
        if "." in s and "e" not in s.lower():
            s = s.rstrip("0").rstrip(".")
        return s
    if isinstance(v, str):
        return json.dumps(v)
    return json.dumps(v)


def scenario_object_from_final(data):
    """Build JS object literal string for one scenario from its _final.json."""
    parts = []
    for k, v in data.items():
        if k in SKIP_KEYS:
            continue
        parts.append(f"        {k}: {js_value(v)}")
    return ",\n".join(parts)


def timeseries_from_array(arr):
    """Build { Key: { series: [...], years: [...] }, ... } from timeseries array."""
    if not arr:
        return {}
    years = [str(row["Year"]) for row in arr]
    keys = [k for k in arr[0].keys() if k not in SKIP_KEYS and k != "Year"]
    out = {}
    for k in keys:
        series = [row[k] for row in arr]
        out[k] = {"series": series, "years": years}
    return out


def format_timeseries_js(name, data):
    """Format timeseries dict as JavaScript const name = { ... };"""
    lines = [f"        const {name} = {{"]
    for key, obj in data.items():
        series = obj["series"]
        years = obj["years"]
        series_str = "[" + ", ".join(js_value(v) for v in series) + "]"
        years_str = "[" + ", ".join(json.dumps(y) for y in years) + "]"
        lines.append(f"            {key}: {{ series: {series_str}, years: {years_str} }},")
    lines.append("        };")
    return "\n".join(lines)


def main():
    # Load scenario data from JSON
    scenario_blocks = {}
    timeseries_data = {}
    for name in SCENARIOS:
        final_path = SCRIPT_DIR / f"{name}_final.json"
        ts_path = SCRIPT_DIR / f"{name}_timeseries.json"
        if not final_path.exists():
            raise FileNotFoundError(f"Missing {final_path}")
        if not ts_path.exists():
            raise FileNotFoundError(f"Missing {ts_path}")
        with final_path.open() as f:
            scenario_blocks[name] = json.load(f)
        with ts_path.open() as f:
            arr = json.load(f)
        timeseries_data[name] = timeseries_from_array(arr)

    # Read existing scenarioData.js
    text = SCENARIO_DATA_JS.read_text(encoding="utf-8")

    # Replace the four scenario blocks (continuity through density) inside scenarioData = { ... }
    # Pattern: from "    continuity: {" to the last "    }" before "};" that closes scenarioData.
    # We replace from "    continuity: {" through "    }\n};" (density closing + scenarioData closing)
    # by "    continuity: {\n...},\n    overgrowth: {\n...},\n    degrowth: {\n...},\n    density: {\n...}\n};"

    block_parts = []
    for name in SCENARIOS:
        obj_str = scenario_object_from_final(scenario_blocks[name])
        key = name[0].lower() + name[1:]  # Continuity -> continuity
        block_parts.append(f"    {key}: {{\n{obj_str}\n    }}")
    new_blocks = ",\n".join(block_parts) + "\n};"

    # Find the span to replace: from "    continuity: {" to "};" that closes the scenarioData object
    start_marker = "    continuity: {"
    start = text.find(start_marker)
    if start == -1:
        raise ValueError("Could not find '    continuity: {' in scenarioData.js")
    # Find the matching closing }; for scenarioData (the first "};" after start that is at column 0 or after "    }\n")
    end_marker = "\n};"
    # The scenarioData literal ends with "    }\n};" (density's } then scenarioData's };)
    end_cand = text.find(end_marker, start)
    if end_cand == -1:
        raise ValueError("Could not find closing '};' for scenarioData")
    # We want to replace from start to end_cand + len(end_marker), but we're replacing the four blocks and keeping "};"
    end = end_cand + len(end_marker)
    before = text[:start]
    after = text[end:]
    # New middle is the four blocks + "};" (we included "};" in new_blocks)
    text = before + new_blocks + after

    # Replace the four timeseries consts and assignments
    # From "        // Timeseries data for projected scenarios" or "        const continuityTimeseries = {"
    # to "    scenarioData.density.timeseriesData = densityTimeseries;"
    ts_start_marker = "        const continuityTimeseries = {"
    ts_start = text.find(ts_start_marker)
    if ts_start == -1:
        raise ValueError("Could not find 'const continuityTimeseries = {' in scenarioData.js")
    ts_end_marker = "scenarioData.density.timeseriesData = densityTimeseries;"
    ts_end = text.find(ts_end_marker)
    if ts_end == -1:
        raise ValueError("Could not find 'scenarioData.density.timeseriesData = densityTimeseries;'")
    ts_end += len(ts_end_marker)

    new_ts_parts = []
    for name in SCENARIOS:
        key = name[0].lower() + name[1:]
        var_name = key + "Timeseries"
        new_ts_parts.append(format_timeseries_js(var_name, timeseries_data[name]))
    new_ts_parts.append("")
    new_ts_parts.append("    // Add timeseries data to scenarios")
    for name in SCENARIOS:
        key = name[0].lower() + name[1:]
        new_ts_parts.append(f"    scenarioData.{key}.timeseriesData = {key}Timeseries;")
    new_ts_section = "\n".join(new_ts_parts)

    text = text[:ts_start] + new_ts_section + text[ts_end:]

    SCENARIO_DATA_JS.write_text(text, encoding="utf-8")
    print(f"Updated {SCENARIO_DATA_JS}")


if __name__ == "__main__":
    main()
