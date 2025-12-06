"""
Render rivers from HydroRIVERS GeoDB
"""

import json
import os
import random
import zipfile
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt


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
    print(f"CRS: {gdf.crs}")
    print(f"Columns: {gdf.columns.tolist()}")

    return gdf


def filter_sri_lanka(gdf):
    """Filter rivers within Sri Lanka's bounding box"""
    # Sri Lanka approximate bounding box
    lon_min, lon_max = 79.5, 82.0
    lat_min, lat_max = 5.9, 10.0

    print("Filtering for Sri Lanka region...")  # Fixed f-string issue

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


def render_rivers(gdf, output_path=None):
    """
    Render the rivers on a map using colors proportional to their lengths,
    highlight the longest river in the darkest blue, and annotate with river
    names from riv_id_to_name.json (if available) at the mouth of the river
    (identified by NEXT_DOWN = 0).
    """
    print("Rendering rivers...")
    print("GeoDataFrame columns:", gdf.columns.tolist())
    print("Sample data:")
    print(gdf.head())

    # Load river ID to name mapping
    riv_id_to_name_path = (
        Path(__file__).parent.parent / "data/static/riv_id_to_name.json"
    )
    with open(riv_id_to_name_path, "r", encoding="utf-8") as f:
        riv_id_to_name = json.load(f)

    fig, ax = plt.subplots(figsize=(16, 16))

    # Reproject to a projected CRS for accurate length calculations
    if gdf.crs.is_geographic:
        # Shortened the long print statement
        print("Reprojecting to a projected CRS for accurate calculations...")
        gdf = gdf.to_crs(epsg=32644)  # UTM Zone 44N, suitable for Sri Lanka

    # Assign random colors to each river using the 'hsv' colormap
    unique_rivers = gdf["MAIN_RIV"].unique()
    # Corrected colormap assignment and split into multiple lines for readability
    color_map = {
        river: plt.cm.get_cmap("hsv")(random.random())
        for river in unique_rivers
    }
    gdf["color"] = gdf["MAIN_RIV"].map(color_map)

    # Sort rivers by the order of their appearance in the dataset
    sorted_groups = gdf.groupby("MAIN_RIV")

    # Plot rivers with their length-proportional colors
    for river, group in sorted_groups:
        group_color = group["color"].iloc[0]
        group.plot(
            ax=ax,
            linewidth=2,
            color=group_color,
            alpha=1,
            label=str(river),
        )

        # Annotate the map with river names (if available) at the mouth
        river_name = riv_id_to_name.get(str(river), None)
        if river_name:
            # Find the row where NEXT_DOWN = 0 (mouth of the river)
            mouth_row = group[group["NEXT_DOWN"] == 0]
            if not mouth_row.empty:
                mouth_row = mouth_row.iloc[0]
                if mouth_row.geometry.type == "LineString":
                    x, y = mouth_row.geometry.coords[-1]  # Mouth of the river
                else:
                    x, y = mouth_row.geometry.centroid.xy
                    x, y = x[0], y[0]
                ax.text(
                    x,
                    y,
                    river_name,
                    fontsize=12,
                    color="black",
                )

    # Remove axis labels, grid, and outer border
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    plt.title("Rivers of Sri Lanka", fontsize=32)
    for spine in ax.spines.values():
        spine.set_visible(False)

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"Saved to {output_path}")

    plt.show()
    print("Done!")


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

    # Render
    output_path = data_path.parent / "lk_rivers_map.png"
    render_rivers(gdf_lk, output_path)


if __name__ == "__main__":
    main()
