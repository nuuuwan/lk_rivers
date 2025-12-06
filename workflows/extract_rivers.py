import json
from pathlib import Path

# Define paths
DATA_DIR = Path("data")
GEOJSON_FILE = DATA_DIR / "sri_lanka_rivers.geojson"
OUTPUT_DIR = DATA_DIR / "rivers"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_rivers():
    """Extract GeoJSON files for each major river identified by MAIN_RIV."""
    # Load the GeoJSON file
    with open(GEOJSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Group features by MAIN_RIV
    rivers = {}
    for feature in data.get("features", []):
        # Convert MultiLineString to LineString if it contains only one line
        geometry = feature.get("geometry")
        if geometry and geometry["type"] == "MultiLineString":
            if len(geometry["coordinates"]) == 1:
                geometry["type"] = "LineString"
                geometry["coordinates"] = geometry["coordinates"][0]

        main_riv = feature["properties"].get("MAIN_RIV")
        if main_riv:
            if main_riv not in rivers:
                rivers[main_riv] = []
            rivers[main_riv].append(feature)

    # Write each group to a separate GeoJSON file
    for main_riv, features in rivers.items():
        output_file = OUTPUT_DIR / f"{main_riv}.geojson"
        river_geojson = {"type": "FeatureCollection", "features": features}
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(river_geojson, f, ensure_ascii=False, indent=4)
        print(f"Extracted: {output_file}")


if __name__ == "__main__":
    extract_rivers()
