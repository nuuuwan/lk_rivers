"""
Render rivers from HydroRIVERS GeoDB
"""

import os
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

    print(f"Filtering for Sri Lanka region...")

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
    """Render the rivers on a map"""
    print("Rendering rivers...")
    print("GeoDataFrame columns:", gdf.columns.tolist())
    print("Sample data:")
    print(gdf.head())

    fig, ax = plt.subplots(figsize=(12, 16))

    # Plot rivers
    gdf.plot(ax=ax, linewidth=0.5, edgecolor="blue", alpha=0.7)

    # Remove axis labels, grid, and outer border
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Annotate major rivers if possible
    major_name_fields = ["name", "NAME", "RiverName", "RIVER_NAME"]
    name_field = None
    for field in major_name_fields:
        if field in gdf.columns:
            name_field = field
            break

    if name_field:
        # Annotate all rivers with their names
        for idx, row in gdf.iterrows():
            if not row.get(name_field):
                continue
            geom = row.geometry
            if geom.type == "LineString":
                x, y = geom.interpolate(0.5, normalized=True).xy
            else:
                x, y = geom.centroid.xy
            ax.text(
                x[0],
                y[0],
                str(row[name_field]),
                fontsize=8,
                color="darkred",
                weight="bold",
            )

    plt.tight_layout()

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
