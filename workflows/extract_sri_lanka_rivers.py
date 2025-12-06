"""
Extract Sri Lankan rivers from HydroRIVERS GeoDB and save as GeoJSON
"""

import os
import zipfile
from pathlib import Path

import geopandas as gpd


def get_data_path():
    """Get the path to the data directory"""
    return Path(__file__).parent.parent / "data"


def extract_gdb(zip_path, extract_to):
    """Extract the geodatabase from zip file"""
    print(f"Extracting {zip_path}...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)
    print(f"Extracted to {extract_to}")


def load_rivers(gdb_path):
    """Load rivers from geodatabase"""
    print(f"Loading rivers from {gdb_path}...")

    # List all layers in the geodatabase
    layers = gpd.list_layers(gdb_path)
    print(f"Available layers: {layers['name'].tolist()}")

    # Load the first layer (usually the rivers layer)
    layer_name = layers.iloc[0]["name"]
    print(f"Loading layer: {layer_name}")
    gdf = gpd.read_file(gdb_path, layer=layer_name)

    print(f"Loaded {len(gdf)} features")
    return gdf


def filter_sri_lanka(gdf):
    """Filter rivers within Sri Lanka's bounding box"""
    # Sri Lanka approximate bounding box
    lon_min, lon_max = 79.5, 82.0
    lat_min, lat_max = 5.9, 10.0

    print("Filtering for Sri Lanka region...")

    # Filter by bounding box
    mask = (
        (gdf.bounds["minx"] >= lon_min)
        & (gdf.bounds["maxx"] <= lon_max)
        & (gdf.bounds["miny"] >= lat_min)
        & (gdf.bounds["maxy"] <= lat_max)
    )

    gdf_lk = gdf[mask].copy()
    print(f"Filtered to {len(gdf_lk)} features in Sri Lanka region")

    return gdf_lk


def save_as_geojson(gdf, output_path):
    """Save GeoDataFrame as GeoJSON"""
    print(f"Saving GeoJSON to {output_path}...")
    gdf.to_file(output_path, driver="GeoJSON")
    print("GeoJSON saved successfully.")


def main():
    """Main execution"""
    data_path = get_data_path()
    zip_path = data_path / "HydroRIVERS_v10_as.gdb.zip"
    extract_path = data_path / "extracted"
    gdb_name = "HydroRIVERS_v10_as.gdb"
    gdb_path = extract_path / gdb_name

    # Extract if not already extracted
    if not gdb_path.exists():
        extract_path.mkdir(exist_ok=True)
        extract_gdb(zip_path, extract_path)
    else:
        print(f"GeoDB already extracted at {gdb_path}")

    # Load rivers
    gdf = load_rivers(str(gdb_path))

    # Filter for Sri Lanka
    gdf_lk = filter_sri_lanka(gdf)

    # Save as GeoJSON
    output_path = data_path / "sri_lanka_rivers.geojson"
    save_as_geojson(gdf_lk, output_path)


if __name__ == "__main__":
    main()
