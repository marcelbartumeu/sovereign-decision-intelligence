"""
OpenStreetMap physical layer ingestion via Overpass API.

Maps the physical reality of an AOI: infrastructure, services, mobility networks,
and land-use types. This forms the "what exists here" layer that differentiates
Boston from Madagascar — the structural affordances available to agents.

Overpass API: https://overpass-api.de/
No authentication required. Rate-limited; use sparingly in production.

Physical layer categories
─────────────────────────
HEALTHCARE      hospitals, clinics, pharmacies, dentists
EDUCATION       universities, schools, kindergartens, libraries
COMMERCE        supermarkets, markets, malls, shops, banks
MOBILITY        bus_stop, tram_stop, subway_entrance, taxi, bicycle_rental
LEISURE         parks, sports centres, cinemas, restaurants, bars, cafes
CIVIC           town_hall, police, post_office, social_facility, place_of_worship
EMPLOYMENT      offices, industrial areas, commercial zones (from landuse)
HOUSING         residential areas, apartments (from landuse + building tags)

Each category informs which H3 cells have access to which affordances,
which in turn shapes agent daily schedules and mobility patterns.
"""

from __future__ import annotations
import time
import requests
from dataclasses import dataclass, field

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

CATEGORY_QUERIES: dict[str, str] = {
    "healthcare": '[amenity~"hospital|clinic|pharmacy|dentist|doctors"]',
    "education":  '[amenity~"university|school|kindergarten|library|college"]',
    "commerce":   '[shop~"supermarket|mall|convenience|department_store"] [amenity~"bank|marketplace"]',
    "transit":    '[highway="bus_stop"] [amenity~"bus_station|taxi|bicycle_rental"] [railway~"tram_stop|subway_entrance"]',
    "leisure":    '[leisure~"park|sports_centre|playground"] [amenity~"cinema|theatre|restaurant|bar|cafe"]',
    "civic":      '[amenity~"townhall|police|post_office|social_facility|place_of_worship|courthouse"]',
    "employment": '[landuse~"commercial|industrial|retail|office"]',
    "housing":    '[landuse~"residential"] [building~"apartments|residential|house"]',
}

# Simplified single-pass query structure
CATEGORY_TAGS: dict[str, list[tuple[str, str]]] = {
    "healthcare": [("amenity", "hospital"), ("amenity", "clinic"), ("amenity", "pharmacy"),
                   ("amenity", "dentist"), ("amenity", "doctors")],
    "education":  [("amenity", "university"), ("amenity", "school"), ("amenity", "kindergarten"),
                   ("amenity", "library"), ("amenity", "college")],
    "commerce":   [("shop", "supermarket"), ("amenity", "marketplace"), ("amenity", "bank"),
                   ("shop", "mall"), ("shop", "department_store"), ("shop", "convenience")],
    "transit":    [("highway", "bus_stop"), ("amenity", "bus_station"), ("amenity", "taxi"),
                   ("railway", "tram_stop"), ("railway", "subway_entrance"),
                   ("amenity", "bicycle_rental")],
    "leisure":    [("leisure", "park"), ("leisure", "sports_centre"), ("amenity", "cinema"),
                   ("amenity", "restaurant"), ("amenity", "bar"), ("amenity", "cafe"),
                   ("amenity", "theatre"), ("leisure", "playground")],
    "civic":      [("amenity", "townhall"), ("amenity", "police"), ("amenity", "post_office"),
                   ("amenity", "social_facility"), ("amenity", "place_of_worship")],
}


@dataclass
class PhysicalFeature:
    osm_id: int
    osm_type: str      # node | way | relation
    category: str
    tags: dict[str, str]
    lat: float
    lon: float
    name: str = ""

    @property
    def coordinates(self) -> tuple[float, float]:
        return (self.lat, self.lon)


@dataclass
class PhysicalLayer:
    """All physical features extracted for an AOI."""
    iso3: str
    features: list[PhysicalFeature] = field(default_factory=list)

    def by_category(self, category: str) -> list[PhysicalFeature]:
        return [f for f in self.features if f.category == category]

    def summary(self) -> dict[str, int]:
        cats: dict[str, int] = {}
        for f in self.features:
            cats[f.category] = cats.get(f.category, 0) + 1
        return cats

    def to_context_string(self) -> str:
        s = self.summary()
        lines = ["Physical infrastructure present in AOI:"]
        labels = {
            "healthcare":  "Healthcare facilities",
            "education":   "Educational institutions",
            "commerce":    "Commercial / retail nodes",
            "transit":     "Public transit stops",
            "leisure":     "Leisure & hospitality venues",
            "civic":       "Civic & government facilities",
        }
        for cat, label in labels.items():
            count = s.get(cat, 0)
            lines.append(f"  {label}: {count}")
        return "\n".join(lines)


class OSMClient:
    """
    Overpass API client for extracting physical features from an AOI bounding box.

    For production use, consider:
      - Overpass Turbo for query development: https://overpass-turbo.eu/
      - Self-hosted Overpass instance for high-volume queries
      - osmium + pyosmium for bulk country extracts
    """

    def __init__(self, timeout: int = 60, retry_delay: float = 5.0):
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "HumanizedABM-Pipeline/1.0"

    def _bbox_from_geojson(self, geojson: dict) -> tuple[float, float, float, float]:
        """Extract (south, west, north, east) bounding box from a GeoJSON polygon."""
        geom = geojson
        if geom.get("type") == "Feature":
            geom = geom["geometry"]
        if geom.get("type") == "FeatureCollection":
            geom = geom["features"][0]["geometry"]

        coords = geom["coordinates"][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return (min(lats), min(lons), max(lats), max(lons))

    def _build_query(self, bbox: tuple, categories: list[str]) -> str:
        s, w, n, e = bbox
        bbox_str = f"{s},{w},{n},{e}"
        parts = ["[out:json][timeout:60];("]
        for cat in categories:
            for k, v in CATEGORY_TAGS.get(cat, []):
                parts.append(f'  node["{k}"="{v}"]({bbox_str});')
                parts.append(f'  way["{k}"="{v}"]({bbox_str});')
        parts.append("); out center;")
        return "\n".join(parts)

    def _parse_element(self, el: dict, category: str) -> PhysicalFeature | None:
        tags = el.get("tags", {})
        osm_type = el.get("type", "node")

        if osm_type == "node":
            lat, lon = el.get("lat", 0.0), el.get("lon", 0.0)
        elif osm_type == "way":
            center = el.get("center", {})
            lat, lon = center.get("lat", 0.0), center.get("lon", 0.0)
        else:
            return None

        if lat == 0.0 and lon == 0.0:
            return None

        return PhysicalFeature(
            osm_id=el["id"],
            osm_type=osm_type,
            category=category,
            tags=tags,
            lat=lat,
            lon=lon,
            name=tags.get("name", tags.get("name:en", "")),
        )

    def fetch(self, geojson: dict, categories: list[str] | None = None) -> PhysicalLayer:
        """
        Fetch all physical features within the AOI bounding box.

        Parameters
        ----------
        geojson    : AOI GeoJSON (Feature or FeatureCollection with Polygon)
        categories : subset of CATEGORY_TAGS keys; None = all categories

        Returns
        -------
        PhysicalLayer with all matched features
        """
        cats = categories or list(CATEGORY_TAGS.keys())
        bbox = self._bbox_from_geojson(geojson)
        query = self._build_query(bbox, cats)

        # Determine iso3 from geojson properties if available
        iso3 = ""
        if geojson.get("type") == "Feature":
            iso3 = geojson.get("properties", {}).get("iso3", "")

        for attempt in range(3):
            try:
                resp = self.session.post(
                    OVERPASS_URL,
                    data={"data": query},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt == 2:
                    raise
                print(f"  Overpass retry {attempt + 1}/3: {exc}")
                time.sleep(self.retry_delay)

        data = resp.json()
        features: list[PhysicalFeature] = []

        # Assign category by matching tags
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            assigned = _assign_category(tags, cats)
            if assigned:
                feat = self._parse_element(el, assigned)
                if feat:
                    features.append(feat)

        return PhysicalLayer(iso3=iso3, features=features)


def _assign_category(tags: dict[str, str], allowed_cats: list[str]) -> str | None:
    for cat in allowed_cats:
        for k, v in CATEGORY_TAGS.get(cat, []):
            if tags.get(k) == v:
                return cat
    return None
