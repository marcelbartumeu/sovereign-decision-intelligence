"""
Generate tourism GeoJSON files for the dashboard from cdm-server-maqueta XML assets.
Outputs to dashboard/public/:
  tourism_peaks.geojson       — mountain peaks (Pics.xml, OGR/GML)
  tourism_refuges.geojson     — mountain refuges (Refuges.xml, GPX)
  tourism_attractions.geojson — imprescindibles (Imprescindibles.xml, custom XML)
  tourism_btt.geojson         — BTT mountain bike trails (BTT/*.xml, GPX tracks)
  tourism_cycling.geojson     — cycling routes (Cicloturisme/*.xml, GPX tracks)
  tourism_corona_llacs.geojson— Corona de Llacs stages (CoronaLlacs/Etapa_*.xml, GPX)
  tourism_ski.geojson         — ski resorts (hardcoded, no coordinate data in CDM)
"""
import json
import pathlib
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).parent
CDM  = HERE.parent.parent / "cdm-server-maqueta" / "Assets" / "Resources" / "Coords"
OUT  = HERE.parent / "dashboard" / "public"
OUT.mkdir(parents=True, exist_ok=True)

NS_GML = "http://www.opengis.net/gml/3.2"
NS_OGR = "http://ogr.maptools.org/"
NS_GPX  = "http://www.topografix.com/GPX/1/1"
NS_GPX0 = "http://www.topografix.com/GPX/1/0"


# ── helpers ──────────────────────────────────────────────────────────────────

def feat(geometry, props):
    return {"type": "Feature", "geometry": geometry, "properties": props}

def point(lon, lat):
    return {"type": "Point", "coordinates": [lon, lat]}

def linestring(coords):
    return {"type": "LineString", "coordinates": coords}

def write_geojson(path, features):
    fc = {"type": "FeatureCollection", "features": features}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  wrote {len(features):4d} features → {path.name}")


# ── 1. Mountain peaks (OGR/GML) ──────────────────────────────────────────────

def parse_peaks():
    tree = ET.parse(CDM / "Pics.xml")
    root = tree.getroot()
    features = []
    for fm in root.findall(f"{{{NS_OGR}}}featureMember"):
        q = fm.find(f"{{{NS_OGR}}}q")
        if q is None:
            continue
        pos_el = q.find(f".//{{{NS_GML}}}pos")
        if pos_el is None or not pos_el.text:
            continue
        lat_s, lon_s = pos_el.text.strip().split()
        lat, lon = float(lat_s), float(lon_s)

        nom   = (q.findtext(f"{{{NS_OGR}}}NOM_PICS") or "").strip()
        alt   = q.findtext(f"{{{NS_OGR}}}ALCADA") or ""
        refugi= (q.findtext(f"{{{NS_OGR}}}REFUGIS") or "").strip()
        features.append(feat(point(lon, lat), {
            "name": nom,
            "altitude": int(alt) if alt else None,
            "refugi": refugi,
        }))
    return features


# ── 2. Mountain refuges (GPX 1.1) ────────────────────────────────────────────

def parse_refuges():
    tree = ET.parse(CDM / "Refuges.xml")
    root = tree.getroot()
    ns = NS_GPX
    features = []
    for wpt in root.findall(f"{{{ns}}}wpt"):
        lat = float(wpt.get("lat"))
        lon = float(wpt.get("lon"))
        nom    = (wpt.findtext(f"{{{ns}}}nom") or
                  wpt.findtext(f"{{{ns}}}name") or "").strip()
        tipus  = (wpt.findtext(f"{{{ns}}}tipus") or "").strip()
        altitud= wpt.findtext(f"{{{ns}}}altitud") or ""
        equip  = (wpt.findtext(f"{{{ns}}}equipament") or "").strip()
        cal    = (wpt.findtext(f"{{{ns}}}calendari") or "").strip()
        info   = (wpt.findtext(f"{{{ns}}}info") or "").strip()
        features.append(feat(point(lon, lat), {
            "name": nom,
            "tipus": tipus,
            "altitude": int(altitud) if altitud else None,
            "equipament": equip,
            "calendari": cal,
            "info": info,
        }))
    return features


# ── 3. Imprescindibles (custom XML) ──────────────────────────────────────────

def parse_attractions():
    tree = ET.parse(CDM / "Imprescindibles.xml")
    root = tree.getroot()
    features = []
    for imp in root.findall("imp"):
        coord_el = imp.find("coord")
        if coord_el is None or not coord_el.text:
            continue
        parts = coord_el.text.strip().split(";")
        if len(parts) < 2:
            continue
        lat, lon = float(parts[0]), float(parts[1])
        name = (imp.findtext("name") or "").strip()
        par  = (imp.findtext("par")  or "").strip()
        features.append(feat(point(lon, lat), {
            "name": name,
            "parish": par,
        }))
    return features


# ── 4. GPX track/route parser (shared by BTT, Cicloturisme, CoronaLlacs) ─────

def _collect_pts(container, pt_tag, ns):
    coords = []
    for pt in container.findall(f"{{{ns}}}{pt_tag}"):
        lat = float(pt.get("lat"))
        lon = float(pt.get("lon"))
        ele_el = pt.find(f"{{{ns}}}ele")
        ele = float(ele_el.text) if ele_el is not None and ele_el.text else None
        coords.append([lon, lat, ele] if ele is not None else [lon, lat])
    return coords

def parse_gpx_track(path, extra_props=None):
    tree = ET.parse(path)
    root = tree.getroot()
    ns = NS_GPX if NS_GPX in root.tag else NS_GPX0

    features = []

    # tracks (trk / trkseg / trkpt)
    for trk in root.findall(f"{{{ns}}}trk"):
        name = (trk.findtext(f"{{{ns}}}name") or path.stem).strip()
        coords = []
        for seg in trk.findall(f"{{{ns}}}trkseg"):
            coords.extend(_collect_pts(seg, "trkpt", ns))
        if coords:
            props = {"name": name}
            if extra_props:
                props.update(extra_props)
            features.append(feat(linestring(coords), props))

    # routes (rte / rtept)
    for rte in root.findall(f"{{{ns}}}rte"):
        name = (rte.findtext(f"{{{ns}}}name") or path.stem).strip()
        coords = _collect_pts(rte, "rtept", ns)
        if coords:
            props = {"name": name}
            if extra_props:
                props.update(extra_props)
            features.append(feat(linestring(coords), props))

    return features


# ── 5. BTT trails ─────────────────────────────────────────────────────────────

def parse_btt():
    features = []
    btt_dir = CDM / "BTT"
    for xml_file in sorted(btt_dir.glob("*.xml")):
        features.extend(parse_gpx_track(xml_file, {"layer": "btt"}))
    return features


# ── 6. Cycling routes ─────────────────────────────────────────────────────────

def parse_cycling():
    features = []
    ciclo_dir = CDM / "Cicloturisme"
    for xml_file in sorted(ciclo_dir.glob("*.xml")):
        features.extend(parse_gpx_track(xml_file, {"layer": "cycling"}))
    return features


# ── 7. Corona de Llacs stages ─────────────────────────────────────────────────

def parse_corona_llacs():
    features = []
    cl_dir = CDM / "CoronaLlacs"
    stage_colors = ["#f59e0b", "#10b981", "#3b82f6", "#ec4899", "#a855f7"]
    for i, xml_file in enumerate(sorted(cl_dir.glob("Etapa_*.xml"))):
        stage_num = i + 1
        for f2 in parse_gpx_track(xml_file):
            f2["properties"]["stage"] = stage_num
            f2["properties"]["color"] = stage_colors[i % len(stage_colors)]
            f2["properties"]["layer"] = "corona_llacs"
            features.append(f2)
    return features


# ── 8. Ski resorts (hardcoded — no coordinate data in CDM project) ────────────

SKI_RESORTS = [
    {
        "name": "Grandvalira – Pas de la Casa",
        "lat": 42.5422, "lon": 1.7334,
        "pistes_km": 210, "max_alt": 2640, "min_alt": 1710,
        "sectors": ["Pas de la Casa", "Grau Roig", "Soldeu", "El Tarter", "Encamp", "Canillo"],
    },
    {
        "name": "Vallnord – Pal Arinsal",
        "lat": 42.5730, "lon": 1.4850,
        "pistes_km": 63, "max_alt": 2560, "min_alt": 1550,
        "sectors": ["Pal", "Arinsal"],
    },
    {
        "name": "Ordino Arcalís",
        "lat": 42.6330, "lon": 1.4720,
        "pistes_km": 30, "max_alt": 2625, "min_alt": 1940,
        "sectors": ["Arcalís"],
    },
]

def parse_ski():
    features = []
    for r in SKI_RESORTS:
        features.append(feat(point(r["lon"], r["lat"]), {
            "name": r["name"],
            "pistes_km": r["pistes_km"],
            "max_alt": r["max_alt"],
            "min_alt": r["min_alt"],
            "sectors": ", ".join(r["sectors"]),
        }))
    return features


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating tourism GeoJSON files...")

    write_geojson(OUT / "tourism_peaks.geojson",       parse_peaks())
    write_geojson(OUT / "tourism_refuges.geojson",     parse_refuges())
    write_geojson(OUT / "tourism_attractions.geojson", parse_attractions())
    write_geojson(OUT / "tourism_btt.geojson",         parse_btt())
    write_geojson(OUT / "tourism_cycling.geojson",     parse_cycling())
    write_geojson(OUT / "tourism_corona_llacs.geojson",parse_corona_llacs())
    write_geojson(OUT / "tourism_ski.geojson",         parse_ski())

    print("Done.")
