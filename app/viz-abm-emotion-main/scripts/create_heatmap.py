import geojson
import h3
from statistics import mean
import sys

# --- Configuration ---
INPUT_GEOJSON = 'public/emotions_summary_full.geojson'
OUTPUT_GEOJSON = 'public/h3_heatmap.geojson'
H3_RESOLUTION = 12
# ---

def calculate_goodness(properties):
    """Calculates the 'goodness' score based on emotion properties."""
    try:
        # Positive contributors
        joy = properties.get('joy', 0)
        safety = properties.get('safety', 0)
        vitality = properties.get('vitality', 0)
        love = properties.get('love', 0)
        vibrancy = properties.get('vibrancy', 0)

        # Negative contributors
        sadness = properties.get('sadness', 0)
        anger = properties.get('anger', 0)
        disgust = properties.get('disgust', 0)
        stress = properties.get('stress', 0)

        # Normalize novelty and prestige? For now, they are not included as per the plan.
        # novelty = properties.get('novelty', 0)
        # prestige = properties.get('prestige', 0)

        positive_score = joy + safety + vitality + love + vibrancy
        negative_score = sadness + anger + disgust + stress

        return positive_score - negative_score
    except TypeError as e:
        print(f"Warning: Skipping feature due to invalid property type: {e} in properties {properties}", file=sys.stderr)
        return None


def main():
    print(f"Reading input GeoJSON: {INPUT_GEOJSON}")
    try:
        with open(INPUT_GEOJSON, 'r') as f:
            data = geojson.load(f)
    except FileNotFoundError:
        print(f"Error: Input file not found at {INPUT_GEOJSON}", file=sys.stderr)
        sys.exit(1)
    except geojson.GeoJSONDecodeError as e:
        print(f"Error decoding GeoJSON: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, geojson.FeatureCollection):
        print("Error: Input GeoJSON must be a FeatureCollection.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(data['features'])} features...")

    h3_scores = {} # {h3_index: [list_of_scores]}

    for feature in data['features']:
        if not isinstance(feature.get('geometry'), geojson.Point):
            # print(f"Warning: Skipping non-Point feature: {feature.get('id', 'N/A')}", file=sys.stderr)
            continue

        coords = feature['geometry']['coordinates']
        properties = feature.get('properties', {})

        if not properties:
            # print(f"Warning: Skipping feature with missing properties: {feature.get('id', 'N/A')}", file=sys.stderr)
            continue

        # GeoJSON coords are lon, lat; h3 needs lat, lon
        lon, lat = coords
        h3_index = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)

        goodness_score = calculate_goodness(properties)

        if goodness_score is not None:
            if h3_index not in h3_scores:
                h3_scores[h3_index] = []
            h3_scores[h3_index].append(goodness_score)

    print(f"Aggregating scores for {len(h3_scores)} unique H3 hexagons at resolution {H3_RESOLUTION}...")

    output_features = []
    for h3_index, scores in h3_scores.items():
        if not scores:
            continue # Should not happen based on current logic, but good practice

        avg_score = mean(scores)
        # h3.h3_to_geo_boundary returns tuples of (lat, lon)
        # GeoJSON requires (lon, lat)
        boundary_lat_lon = h3.cell_to_boundary(h3_index)
        boundary_lon_lat = [(lon, lat) for lat, lon in boundary_lat_lon]
        # Close the loop for GeoJSON Polygon
        boundary_lon_lat.append(boundary_lon_lat[0])

        hexagon_poly = geojson.Polygon([boundary_lon_lat])

        output_features.append(geojson.Feature(
            geometry=hexagon_poly,
            properties={
                "h3_index": h3_index,
                "avg_goodness_score": avg_score,
                "point_count": len(scores)
            }
        ))

    output_feature_collection = geojson.FeatureCollection(output_features)

    print(f"Writing output GeoJSON: {OUTPUT_GEOJSON}")
    try:
        with open(OUTPUT_GEOJSON, 'w') as f:
            geojson.dump(output_feature_collection, f, indent=2) # Use indent for readability
    except IOError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)

    print("Done.")

if __name__ == "__main__":
    # Ensure necessary libraries are installed
    try:
        import h3
        import geojson
    except ImportError as e:
        print(f"Error: Missing required library. Please install 'h3-py' and 'geojson'. ({e})", file=sys.stderr)
        print("You can install them using: pip install h3 geojson", file=sys.stderr)
        sys.exit(1)

    main() 