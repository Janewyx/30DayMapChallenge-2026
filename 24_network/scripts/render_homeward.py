# %% [markdown]
# # Homeward · Vancouver traffic at 16:00
#
# Lights each measured site in the spring 2018 16:00–17:00 composite from the
# inventory notebook: Vancouver intersections, the two West Vancouver approaches
# and both bridge crossings. Each glow is the median of the site's counts in that
# clock hour across its surveyed weekdays. The basemap is OpenStreetMap roads,
# shoreline and inland water, cached under data/raw/osm on the first run.
#
# Run from the day folder: `.venv/bin/python scripts/render_homeward.py`

# %% Setup
import argparse
from functools import partial
import json
import sys
from pathlib import Path

import matplotlib

try:
    get_ipython().run_line_magic("load_ext", "autoreload")  # noqa: F821
    get_ipython().run_line_magic("autoreload", "2")  # noqa: F821
except NameError:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from PIL import Image
from pyproj import Transformer
from shapely.geometry import Point
from shapely.ops import unary_union

script_dir = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd() / "scripts"
day_dir = script_dir.parent
sys.path.insert(0, str(script_dir))
import homeward_functions as hf  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--config", default=str(script_dir / "homeward_config.yaml"))
options, _ = parser.parse_known_args()
config_path = Path(options.config)

cfg = yaml.safe_load(config_path.read_text())
paths = {key: day_dir / value for key, value in cfg["paths"].items()}
colours = cfg["palette"]
glow = cfg["glow"]
type_pt = cfg["type"]
otf_dir = day_dir.parent / "OTF"
family = hf.register_fonts(otf_dir)
plt.rcParams["font.family"] = family

to_display = Transformer.from_crs(cfg["crs"]["source"], cfg["crs"]["display"], always_xy=True)

# %% Map frame
# The panel is placed in figure fractions; its aspect fixes the extent's height.
fig_w, fig_h = cfg["figure"]["size_in"]
layout = cfg["figure"]
panel_w_in = (layout["map_right"] - layout["map_left"]) * fig_w
panel_h_in = (layout["map_top"] - layout["map_bottom"]) * fig_h
frame, _ = hf.frame_from_centre(
    to_display, cfg["extent"]["centre_lon"], cfg["extent"]["centre_lat"],
    cfg["extent"]["width_km"] * 1000, panel_w_in / panel_h_in,
)
xmin, ymin, xmax, ymax = frame.bounds
print(f"Map extent {(xmax - xmin) / 1000:.1f} × {(ymax - ymin) / 1000:.1f} km")


# %% OpenStreetMap basemap
queries = hf.overpass_queries(cfg["osm"]["bbox"], cfg["osm"]["road_classes"], cfg["osm"]["timeout_s"])
osm = {
    layer: hf.cached_overpass(query, paths["osm_cache"] / f"{layer}.json", cfg["osm"]["endpoints"],
                              cfg["osm"]["timeout_s"], cfg["osm"]["retries"], cfg["osm"]["backoff_s"])
    for layer, query in queries.items()
}
roads = hf.way_lines(osm["roads"], to_display)
coast = hf.way_lines(osm["coastline"], to_display)
# A slightly larger frame keeps the land fill flush with the panel edge.
land = hf.land_from_coastline(coast.geometry.tolist(), frame.buffer(500, join_style=2))
inland_water = hf.water_polygons(osm["water"], to_display)
print(f"{len(roads):,} road ways · {len(coast)} coastline ways · land {land.area / 1e6:.0f} km²")

# %% Measured sites in the 16:00 composite
site_hours = pd.read_csv(paths["site_hours"], dtype={"site_id": str, "physical_id": str})
sites = hf.site_values(site_hours, cfg["selection"]["local_start"], cfg["selection"]["statistic"])

# Place the sites that lack catalogue coordinates.
city_points = json.loads(paths["city_intersections"].read_text())
for physical_id, fill in cfg["coordinate_fills"].items():
    row = sites.physical_id.eq(physical_id)
    if "city_xstreet" in fill:
        lon, lat = hf.city_point(city_points, fill["city_xstreet"])
        sites.loc[row, ["longitude", "latitude"]] = lon, lat
    else:
        crossing = hf.street_crossing(roads, *fill["osm_crossing"])
        sites.loc[row, ["longitude", "latitude"]] = to_display.transform(crossing.x, crossing.y, direction="INVERSE")
assert sites[["longitude", "latitude"]].notna().all().all(), "a site still lacks coordinates"

sites["x"], sites["y"] = to_display.transform(sites.longitude.to_numpy(), sites.latitude.to_numpy())
sites["is_bridge"] = sites.physical_id.isin(cfg["bridges"])
sites["in_frame"] = [frame.contains(Point(x, y)) for x, y in zip(sites.x, sites.y)]
points = sites.loc[~sites.is_bridge]
print(f"{len(points)} intersections ({points.in_frame.sum()} inside the frame) · {sites.is_bridge.sum()} bridges")
print(sites.loc[sites.is_bridge, ["physical_id", "vehicles", "survey_days"]].to_string(index=False))

# Bridge decks from OSM: the road ways carrying each bridge's name.
bridge_decks = {}
for physical_id, bridge in cfg["bridges"].items():
    deck = roads.loc[roads.name.eq(bridge["osm_name"]) & roads.highway.isin(["motorway", "trunk", "primary"])]
    assert len(deck), f"no OSM ways named {bridge['osm_name']}"
    bridge_decks[physical_id] = unary_union(deck.geometry.tolist())

# Area-true dots and width-true lines.
dot_diameter = glow["dot_reference_diameter_pt"] * np.sqrt(points.vehicles / glow["dot_reference_count"])
line_width = {pid: glow["line_reference_width_pt"] * v / glow["line_reference_count"]
              for pid, v in zip(sites.physical_id, sites.vehicles) if pid in cfg["bridges"]}

# %% Plate
fig = plt.figure(figsize=(fig_w, fig_h), facecolor=colours["background"])
ax = fig.add_axes([layout["map_left"], layout["map_bottom"],
                   layout["map_right"] - layout["map_left"], layout["map_top"] - layout["map_bottom"]])
ax.set_facecolor(colours["background"])
ax.set_xlim(xmin, xmax)
ax.set_ylim(ymin, ymax)
ax.set_aspect("equal")
ax.set_axis_off()

hf.plot_polygons(ax, land, facecolor=colours["land"], edgecolor=colours["coastline"], linewidth=0.35, zorder=1)
hf.plot_polygons(ax, inland_water.intersection(frame.buffer(500)), facecolor=colours["water_inland"],
                 edgecolor=colours["coastline"], linewidth=0.3, zorder=2)

for tier in cfg["roads"].values():
    subset = roads.loc[roads.highway.isin(tier["classes"])]
    for line in subset.geometry:
        x, y = line.xy
        ax.plot(x, y, color=colours["roads"], lw=tier["width_pt"], alpha=tier["alpha"],
                solid_capstyle="round", zorder=3)

for physical_id, deck in bridge_decks.items():
    hf.glow_line(ax, deck, line_width[physical_id], glow, colours, zorder=6)
hf.glow_points(ax, points.x, points.y, dot_diameter.to_numpy(), glow, colours, zorder=7)

# Geographic labels.
fonts = {style: hf.font_file(otf_dir, style) for style in ["Leicht", "Buch", "BuchKursiv", "Kräftig"]}
font = partial(hf.font, fonts, family)

for place in cfg["places"]:
    ax.text(*to_display.transform(*place["lonlat"]), hf.spaced(place["text"]), fontproperties=font("Buch", type_pt[place["size"]]),
            color=colours["text"], ha="center", va="center", zorder=9, alpha=0.88)
for water in cfg["water"]:
    ax.text(*to_display.transform(*water["lonlat"]), hf.spaced(water["text"]), fontproperties=font("BuchKursiv", type_pt["water"]),
            color=colours["muted"], ha="center", va="center", linespacing=1.6, zorder=9)
for physical_id, bridge in cfg["bridges"].items():
    site = sites.set_index("physical_id").loc[physical_id]
    x, y = to_display.transform(*bridge["label_lonlat"])
    ax.text(x, y, hf.spaced(bridge["label"]), fontproperties=font("Kräftig", type_pt["bridge_label"]),
            color=colours["text"], ha=bridge["label_ha"], va="bottom", zorder=9)
    ax.text(x, y - cfg["labels"]["bridge_value_gap_m"], f"{site.vehicles:,.0f} vehicles · both directions\nmedian of {site.survey_days} weekdays",
            fontproperties=font("Buch", type_pt["bridge_value"]), color=colours["muted"],
            ha=bridge["label_ha"], va="top", linespacing=0.95, zorder=9)

# Header, aligned to the map panel's rendered left edge.
fig.canvas.draw()
left = ax.get_position().x0
fig.text(left, 0.968, cfg["text"]["eyebrow"], fontproperties=font("Buch", type_pt["eyebrow"]),
         color=colours["muted"], va="top")
fig.text(left - 0.004, 0.952, cfg["text"]["title"], fontproperties=font("Leicht", type_pt["title"]),
         color=colours["text"], va="top")
fig.text(left, 0.878, cfg["text"]["subtitle"], fontproperties=font("Buch", type_pt["subtitle"]),
         color=colours["text"], va="top", alpha=0.85)

# Legend: area-true intersection dots and width-true bridge strokes, in a points-scaled axes.
legend_bottom = layout["map_bottom"] - 0.060
legend_ax = fig.add_axes([left, legend_bottom, layout["map_right"] - left, 0.048])
legend_w_pt = legend_ax.get_position().width * fig_w * 72
legend_h_pt = legend_ax.get_position().height * fig_h * 72
legend_ax.set_xlim(0, legend_w_pt)
legend_ax.set_ylim(0, legend_h_pt)
legend_ax.set_axis_off()
legend_ax.text(0, legend_h_pt, cfg["text"]["legend_title"], fontproperties=font("Kräftig", type_pt["legend_title"]),
               color=colours["text"], va="top")
mark_y = legend_h_pt * 0.30
dot_counts = [500, 2000, 5000]
dot_x = np.array([8, 78, 156])
hf.glow_points(legend_ax, dot_x, np.full(3, mark_y),
               glow["dot_reference_diameter_pt"] * np.sqrt(np.array(dot_counts) / glow["dot_reference_count"]),
               glow, colours, zorder=2)
for x, count in zip(dot_x, dot_counts):
    legend_ax.text(x + 14, mark_y, f"{count:,}", fontproperties=font("Buch", type_pt["legend"]),
                   color=colours["muted"], va="center")
legend_ax.text(dot_x[0] - 6, mark_y - 17, "intersection · incoming vehicles", fontproperties=font("Buch", type_pt["legend"]),
               color=colours["muted"], va="center")
line_x0 = 330
for i, count in enumerate([5000, 10000]):
    x0 = line_x0 + i * 120
    hf.glow_line(legend_ax, hf.LineString([(x0, mark_y), (x0 + 50, mark_y)]),
                 glow["line_reference_width_pt"] * count / glow["line_reference_count"], glow, colours, zorder=2)
    legend_ax.text(x0 + 58, mark_y, f"{count:,}", fontproperties=font("Buch", type_pt["legend"]),
                   color=colours["muted"], va="center")
legend_ax.text(line_x0, mark_y - 17, "bridge · both directions", fontproperties=font("Buch", type_pt["legend"]),
               color=colours["muted"], va="center")

# Footer notes and signature.
footer_top = legend_bottom - 0.018
line_step = type_pt["footer"] * 1.5 / 72 / fig_h
for i, line in enumerate(cfg["text"]["footer"]):
    fig.text(left, footer_top - i * line_step, line, fontproperties=font("Buch", type_pt["footer"]),
             color=colours["muted"], va="top")
fig.text(left, 0.022, cfg["text"]["signature"], fontproperties=font("Buch", type_pt["footer"]),
         color=colours["muted"], va="bottom")

paths["output"].parent.mkdir(parents=True, exist_ok=True)
fig.savefig(paths["output"], dpi=layout["dpi"], facecolor=colours["background"])
plt.close(fig)

# %% Checks and web preview
with Image.open(paths["output"]) as plate:
    print(f"{paths['output'].name}: {plate.size[0]} × {plate.size[1]} px")
    assert plate.size == (fig_w * layout["dpi"], fig_h * layout["dpi"])
    preview_w = layout["preview_width_px"]
    plate.resize((preview_w, round(preview_w * plate.size[1] / plate.size[0])), Image.LANCZOS).save(paths["preview"])
outside = sites.loc[~sites.in_frame, "physical_id"].tolist()
print("Sites outside the frame:", outside or "none")
