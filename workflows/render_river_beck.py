"""
Render a single river in a Harry Beck (London Underground) diagrammatic style.

The river network is simplified to an octilinear schematic: every edge is
snapped to a multiple of 45 degrees. The river is treated as a tree that flows
into its mouth (the segment where NEXT_DOWN == 0), and the layout is grown
outwards from the mouth so that tributaries fan out along the 8 compass
directions like lines on a metro map.
"""

import colorsys
import math
import sys
import webbrowser
from collections import defaultdict, deque
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
from adjustText import adjust_text

from utils_future import File, JSONFile, Log

log = Log("render_river_beck")

DIR_RIVERS = Path("data/rivers")
DIR_STATIC = Path("data/static")

RIV_ID_TO_NAME = JSONFile(str(DIR_STATIC / "riv_id_to_name.json")).read()
LATLNG_TO_NAME = JSONFile(
    str(DIR_STATIC / "latlng_to_location_name.json")
).read()
# Only map names to ids that have a river file, so branch ids sharing a
# river's name never shadow the actual river.
NAME_TO_RIV_ID = {
    name: riv_id
    for riv_id, name in RIV_ID_TO_NAME.items()
    if name and (DIR_RIVERS / f"{riv_id}.geojson").exists()
}

# Octilinear layout: 8 unit directions, each a multiple of 45 degrees.
OCTANTS = [
    (math.cos(math.radians(a)), math.sin(math.radians(a)))
    for a in range(0, 360, 45)
]

LINE_WIDTH = 8.0
CASING_WIDTH = 14.0
JUNCTION_SIZE = 110

# Number of longest branches (metro "lines") to display.
MAX_LINES = 10

# Branch colours ramp through hue by length to the sea: the longest run to a
# terminus at hue 240 (blue), the shortest at hue 0 (red).
HUE_START = 240
HUE_END = 0


def branch_color(fraction):
    """Colour for a branch by its length to the sea (1 = longest)."""
    hue = HUE_END + (HUE_START - HUE_END) * fraction
    return colorsys.hsv_to_rgb(hue / 360, 0.85, 0.8)


def snap_key(point):
    """Snap a coordinate to a hashable key so shared endpoints merge."""
    return (round(point[0], 6), round(point[1], 6))


def resolve_riv_id(arg):
    """Resolve a CLI argument to a river id (accepts an id or a river name)."""
    if arg in RIV_ID_TO_NAME:
        return arg
    if arg in NAME_TO_RIV_ID:
        return NAME_TO_RIV_ID[arg]
    raise ValueError(f"Unknown river '{arg}'. Pass a river id or river name.")


def build_network(features):
    """
    Build the reach graph from river segments.

    Each segment is simplified to a single edge from its upstream endpoint
    (coords[0]) to its downstream endpoint (coords[-1]). Returns the undirected
    adjacency, the node coordinates, a map from each upstream node to its
    segment id, and the mouth node key.
    """
    adjacency = defaultdict(set)
    node_coord = {}
    node_to_hyriv = {}
    node_to_length = {}
    mouth_key = None

    for feature in features:
        coords = feature["geometry"]["coordinates"]
        upstream, downstream = coords[0], coords[-1]
        u_key, d_key = snap_key(upstream), snap_key(downstream)

        node_coord[u_key] = upstream
        node_coord[d_key] = downstream
        node_to_hyriv[u_key] = feature["properties"].get("HYRIV_ID")
        node_to_length[u_key] = feature["properties"].get("LENGTH_KM", 0.0)
        if u_key != d_key:
            adjacency[u_key].add(d_key)
            adjacency[d_key].add(u_key)

        if feature["properties"].get("NEXT_DOWN") == 0:
            mouth_key = d_key

    if mouth_key is None:
        raise ValueError("No mouth segment (NEXT_DOWN == 0) found in river.")

    return adjacency, node_coord, node_to_hyriv, node_to_length, mouth_key


def snap_octant(true_angle_deg, used):
    """
    Snap a true bearing to the nearest free 45-degree octant.

    Keeping octants distinct per node spreads tributaries apart so junctions
    stay legible, mimicking a hand-drawn transit map.
    """
    base = round(true_angle_deg / 45) % 8
    if base not in used:
        used.add(base)
        return base
    for offset in range(1, 8):
        for candidate in ((base + offset) % 8, (base - offset) % 8):
            if candidate not in used:
                used.add(candidate)
                return candidate
    used.add(base)
    return base


def layout_octilinear(adjacency, node_coord, mouth_key):
    """
    Assign octilinear positions by growing the tree outwards from the mouth.

    Real reach lengths (in a local equal-aspect projection) are preserved so
    long rivers stay long, while every edge direction is forced onto a
    multiple of 45 degrees.
    """
    mean_lat = sum(c[1] for c in node_coord.values()) / len(node_coord)
    cos_lat = math.cos(math.radians(mean_lat))

    def planar(key):
        lon, lat = node_coord[key]
        return lon * cos_lat, lat

    pos = {mouth_key: (0.0, 0.0)}
    incoming_octant = {mouth_key: None}
    edges = []
    queue = deque([mouth_key])

    while queue:
        parent = queue.popleft()
        px, py = planar(parent)

        used = set()
        if incoming_octant[parent] is not None:
            used.add((incoming_octant[parent] + 4) % 8)

        children = [c for c in adjacency[parent] if c not in pos]
        children.sort(
            key=lambda c: math.atan2(planar(c)[1] - py, planar(c)[0] - px)
        )

        for child in children:
            cx, cy = planar(child)
            true_angle = math.degrees(math.atan2(cy - py, cx - px))
            length = math.hypot(cx - px, cy - py)

            octant = snap_octant(true_angle, used)
            ux, uy = OCTANTS[octant]
            parent_pos = pos[parent]
            child_pos = (
                parent_pos[0] + ux * length,
                parent_pos[1] + uy * length,
            )
            pos[child] = child_pos
            incoming_octant[child] = octant
            edges.append((parent_pos, child_pos))
            queue.append(child)

    return pos, edges


def build_rooted_tree(adjacency, node_coord, mouth_key):
    """Root the network at the mouth and return planar coords + tree links."""
    mean_lat = sum(c[1] for c in node_coord.values()) / len(node_coord)
    cos_lat = math.cos(math.radians(mean_lat))
    planar = {
        key: (lon * cos_lat, lat) for key, (lon, lat) in node_coord.items()
    }

    parent = {mouth_key: None}
    children = defaultdict(list)
    order = []
    queue = deque([mouth_key])
    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbour in adjacency[node]:
            if neighbour not in parent:
                parent[neighbour] = node
                children[node].append(neighbour)
                queue.append(neighbour)

    return planar, parent, children, order


def edge_length(planar, a, b):
    """Planar distance between two nodes."""
    (ax, ay), (bx, by) = planar[a], planar[b]
    return math.hypot(bx - ax, by - ay)


def decompose_branches(planar, parent, children, order):
    """
    Split the river tree into branches via heavy-path decomposition.

    At each junction the branch continues along the child that reaches the
    farthest source; every other child starts a new branch. Each branch is a
    chain of nodes with a length and the node where it attaches upstream.
    """
    up_len = {}
    heavy = {}
    for node in reversed(order):
        best_len, best_child = 0.0, None
        for child in children[node]:
            candidate = up_len[child] + edge_length(planar, node, child)
            if candidate > best_len:
                best_len, best_child = candidate, child
        up_len[node] = best_len
        heavy[node] = best_child

    branches = []
    for node in order:
        is_head = parent[node] is None or heavy[parent[node]] != node
        if not is_head:
            continue
        chain = [node]
        cursor = node
        while heavy[cursor] is not None:
            cursor = heavy[cursor]
            chain.append(cursor)
        length = sum(
            edge_length(planar, chain[i], chain[i + 1])
            for i in range(len(chain) - 1)
        )
        branches.append(
            {"nodes": chain, "length": length, "attach": parent[node]}
        )
    return branches


def select_branches(branches, max_lines):
    """
    Keep the longest branches while staying connected to the mouth.

    Greedily adds the longest branch whose attachment node already belongs to
    a kept branch, so the diagram never shows a floating tributary.
    """
    main = next(b for b in branches if b["attach"] is None)
    kept = [main]
    kept_nodes = set(main["nodes"])
    while len(kept) < max_lines:
        candidates = [
            b
            for b in branches
            if b not in kept and b["attach"] in kept_nodes
        ]
        if not candidates:
            break
        best = max(candidates, key=lambda b: b["length"])
        kept.append(best)
        kept_nodes.update(best["nodes"])
    return kept


def dist_to_sea(node, parent, node_to_length):
    """Along-river distance in km from a node down to the mouth."""
    total = 0.0
    while parent[node] is not None:
        total += node_to_length.get(node, 0.0)
        node = parent[node]
    return total



def draw_termination_tick(ax, tip, neighbour, color, half):
    """Draw a double-sided tick across a line end, perpendicular to it."""
    (tx, ty), (nx, ny) = tip, neighbour
    dx, dy = tx - nx, ty - ny
    dist = math.hypot(dx, dy) or 1.0
    perp_x, perp_y = -dy / dist, dx / dist
    ax.plot(
        [tx - perp_x * half, tx + perp_x * half],
        [ty - perp_y * half, ty + perp_y * half],
        color=color,
        linewidth=LINE_WIDTH,
        solid_capstyle="round",
        zorder=4,
    )


def render(riv_id, output_path):
    """Render one river as an octilinear Harry Beck style diagram."""
    features = JSONFile(str(DIR_RIVERS / f"{riv_id}.geojson")).read()[
        "features"
    ]
    river_name = RIV_ID_TO_NAME.get(riv_id) or f"River {riv_id}"

    adjacency, node_coord, node_to_hyriv, node_to_length, mouth_key = (
        build_network(features)
    )
    planar, parent, children, order = build_rooted_tree(
        adjacency, node_coord, mouth_key
    )
    branches = decompose_branches(planar, parent, children, order)
    kept = select_branches(branches, MAX_LINES)

    # Restrict the network to the kept branches, then lay it out octilinearly.
    kept_adjacency = defaultdict(set)
    kept_nodes = set()
    for branch in kept:
        nodes = branch["nodes"]
        kept_nodes.update(nodes)
        if branch["attach"] is not None:
            kept_nodes.add(branch["attach"])
            kept_adjacency[branch["attach"]].add(nodes[0])
            kept_adjacency[nodes[0]].add(branch["attach"])
        for a, b in zip(nodes, nodes[1:]):
            kept_adjacency[a].add(b)
            kept_adjacency[b].add(a)
    kept_coord = {key: node_coord[key] for key in kept_nodes}
    pos, _edges = layout_octilinear(kept_adjacency, kept_coord, mouth_key)

    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_facecolor("white")

    # Size line-end ticks relative to a typical edge length.
    edge_lengths = [
        math.hypot(pos[a][0] - pos[b][0], pos[a][1] - pos[b][1])
        for a in kept_adjacency
        for b in kept_adjacency[a]
    ]
    tick_half = (sorted(edge_lengths)[len(edge_lengths) // 2] * 0.45
                 if edge_lengths else 1.0)

    # Colour each branch by the full distance from the sea to its terminus.
    distances = [
        dist_to_sea(branch["nodes"][-1], parent, node_to_length)
        for branch in kept
    ]
    min_distance = min(distances)
    span_distance = (max(distances) - min_distance) or 1.0

    # Rank branches by distance to the sea (longest = #1).
    rank_of = {
        idx: r + 1
        for r, idx in enumerate(
            sorted(range(len(kept)), key=lambda i: distances[i], reverse=True)
        )
    }

    # Location label (name or lat,lng) for a place; opens Maps if unnamed.
    opened = set()
    added_keys = []

    def place_label(coord):
        lon, lat = coord
        key = f"{lat:.2f},{lon:.2f}"
        name = LATLNG_TO_NAME.get(key)
        if name is None:
            # New spot: record a placeholder to be named later.
            LATLNG_TO_NAME[key] = key
            added_keys.append(key)
            name = key
        if name == key and key not in opened:
            opened.add(key)
            webbrowser.open(f"https://www.google.com/maps?q={lat},{lon}")
        return name

    # Collected label texts and points (lines + stations) to push labels off.
    texts = []
    avoid_x, avoid_y = [], []

    for index, branch in enumerate(kept):
        color = branch_color((distances[index] - min_distance) / span_distance)
        chain = branch["nodes"]
        if branch["attach"] is not None:
            # Extend the colour up to the junction so branches visibly meet.
            chain = [branch["attach"]] + chain
        points = [pos[node] for node in chain]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        ax.plot(
            xs, ys,
            color="white",
            linewidth=CASING_WIDTH,
            solid_capstyle="round",
            solid_joinstyle="round",
            zorder=1,
        )
        ax.plot(
            xs, ys,
            color=color,
            linewidth=LINE_WIDTH,
            solid_capstyle="round",
            solid_joinstyle="round",
            zorder=2,
        )

        # Sample the line so labels can be pushed clear of it later.
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            steps = max(
                2, int(math.hypot(x1 - x0, y1 - y0) / (tick_half * 0.5))
            )
            avoid_x.extend(np.linspace(x0, x1, steps))
            avoid_y.extend(np.linspace(y0, y1, steps))

        # Termination tick at the upstream source of each branch.
        source = branch["nodes"][-1]
        source_neighbour = (
            branch["nodes"][-2]
            if len(branch["nodes"]) >= 2
            else branch["attach"]
        )
        draw_termination_tick(
            ax, pos[source], pos[source_neighbour], color, tick_half
        )

        # Termination label: place name / lat,lng plus distance from the sea.
        distance = distances[index]
        sx, sy = pos[source]
        avoid_x.append(sx)
        avoid_y.append(sy)
        texts.append(ax.text(
            sx, sy,
            f"#{rank_of[index]} {place_label(node_coord[source])}"
            f"\n({distance:.0f} km)",
            fontsize=9,
            color="black",
            ha="center",
            va="center",
            zorder=6,
        ))

        # Branch name, on the midpoint of its last (source) segment.
        source_id = node_to_hyriv.get(source)
        branch_ident = RIV_ID_TO_NAME.get(str(source_id)) or str(source_id)
        (nx, ny), (ex, ey) = pos[source_neighbour], pos[source]
        bx, by = (nx + ex) / 2, (ny + ey) / 2
        texts.append(ax.text(
            bx, by,
            branch_ident,
            fontsize=7,
            fontstyle="italic",
            color="black",
            ha="center",
            va="center",
            zorder=7,
            path_effects=[pe.withStroke(linewidth=2.5, foreground="white")],
        ))

    # Junction symbols: white circle with a black edge at every confluence.
    for node in kept_nodes:
        if len(kept_adjacency[node]) >= 3:
            jx, jy = pos[node]
            ax.scatter(
                jx, jy,
                s=JUNCTION_SIZE,
                facecolor="white",
                edgecolor="black",
                linewidth=2.5,
                zorder=5,
            )
            avoid_x.append(jx)
            avoid_y.append(jy)
            texts.append(ax.text(
                jx, jy,
                place_label(node_coord[node]),
                fontsize=9,
                color="black",
                ha="center",
                va="center",
                zorder=6,
            ))

    # Mouth terminus: a tick plus the sea outlet's place name / lat,lng.
    mouth_neighbour = next(iter(kept_adjacency[mouth_key]))
    draw_termination_tick(
        ax, pos[mouth_key], pos[mouth_neighbour], branch_color(1.0), tick_half
    )
    mx, my = pos[mouth_key]
    avoid_x.append(mx)
    avoid_y.append(my)
    texts.append(ax.text(
        mx, my,
        place_label(node_coord[mouth_key]),
        fontsize=9,
        color="black",
        ha="center",
        va="center",
        zorder=6,
    ))

    # Persist any newly-seen spots so they can be named later.
    if added_keys:
        JSONFile(
            str(DIR_STATIC / "latlng_to_location_name.json")
        ).write(LATLNG_TO_NAME)
        log.info(f"Added {len(added_keys)} latlng(s) to the location file")

    ax.set_aspect("equal")
    ax.axis("off")
    ax.margins(0.05)

    # Titles and footer hug the diagram (axes box shrinks with equal aspect).
    ax.annotate(
        river_name, (0.5, 1.06), xycoords="axes fraction",
        ha="center", va="bottom",
        fontsize=30, fontweight="bold", color="#222222",
    )
    ax.annotate(
        f"{len(kept)} longest branches", (0.5, 1.015), xycoords="axes fraction",
        ha="center", va="bottom",
        fontsize=15, fontstyle="italic", color="#555555",
    )
    ax.annotate(
        "Data source: www.hydrosheds.org   |   "
        "Visualisation & code: www.github.com/nuuuwan/lk_rivers",
        (0.5, -0.04), xycoords="axes fraction",
        ha="center", va="top",
        fontsize=12, color="#555555",
    )

    # Nudge labels so they avoid each other and the river lines.
    adjust_text(
        texts,
        x=avoid_x,
        y=avoid_y,
        ax=ax,
        expand=(1.3, 1.5),
        force_text=(0.5, 0.6),
        force_static=(0.25, 0.3),
        arrowprops=dict(arrowstyle="-", color="0.55", lw=0.5),
        min_arrow_len=6,
    )

    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    log.info(f"Wrote {File(str(output_path))}")


def main(arg):
    """Render the river identified by a river id or river name."""
    riv_id = resolve_riv_id(arg)
    river_file = DIR_RIVERS / f"{riv_id}.geojson"
    if not river_file.exists():
        # Branch ids in the name map have no river file of their own.
        log.warning(f"No river file for {riv_id}; skipping.")
        return
    river_name = RIV_ID_TO_NAME.get(riv_id) or riv_id
    slug = river_name.replace(" ", "_") if river_name else riv_id
    images_dir = Path("images")
    images_dir.mkdir(parents=True, exist_ok=True)
    output_path = images_dir / f"{slug}.harry_beck.png"
    render(riv_id, output_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python render_river_beck.py <river id | name>")
    main(sys.argv[1])
