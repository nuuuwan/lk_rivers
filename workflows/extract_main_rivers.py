"""
Extract Sri Lankan rivers from HydroRIVERS GeoDB and save each MAIN_RIV as a separate GeoJSON file
"""

import os
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon


def get_data_path():
    """Get the path to the data directory"""
    return Path(__file__).parent.parent / "data/source"


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


def get_sri_lanka_polygon():
    """Get the polygon representing Sri Lanka"""
    return Polygon(
        [
            (79.5, 5.9),
            (82.0, 5.9),
            (82.0, 10.0),
            (79.5, 10.0),
            (79.5, 5.9),
        ]
    )


def filter_sri_lanka(gdf):
    """Filter rivers within Sri Lanka using a spatial polygon"""
    sri_lanka_polygon = get_sri_lanka_polygon()
    print("Filtering for Sri Lanka region using spatial polygon...")

    # Ensure GeoDataFrame has a valid CRS
    if gdf.crs is None or gdf.crs.to_string() != "EPSG:4326":
        print("Reprojecting to WGS84 (EPSG:4326)...")
        gdf = gdf.to_crs("EPSG:4326")

    # Spatial filter
    gdf_lk = gdf[gdf.intersects(sri_lanka_polygon)].copy()
    print(f"Filtered to {len(gdf_lk)} features in Sri Lanka region")

    # Repair invalid geometries
    gdf_lk["geometry"] = gdf_lk["geometry"].buffer(0)

    return gdf_lk


def save_main_rivers_as_geojson(gdf, output_dir):
    """Save each MAIN_RIV as a separate GeoJSON file"""
    if "MAIN_RIV" not in gdf.columns:
        print("MAIN_RIV column not found in the dataset.")
        return

    output_dir.mkdir(exist_ok=True)

    main_rivers = gdf["MAIN_RIV"].unique()
    print(f"Found {len(main_rivers)} unique MAIN_RIV values.")

    for main_riv in main_rivers:
        print(f"Processing MAIN_RIV: {main_riv}")
        river_gdf = gdf[gdf["MAIN_RIV"] == main_riv]
        output_path = output_dir / f"main_river_{main_riv}.geojson"
        river_gdf.to_file(output_path, driver="GeoJSON")
        print(f"Saved {main_riv} to {output_path}")


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

    # Save each MAIN_RIV as a separate GeoJSON
    output_dir = Path(__file__).parent.parent / "data/main_rivers"
    save_main_rivers_as_geojson(gdf_lk, output_dir)


if __name__ == "__main__":
    main()
