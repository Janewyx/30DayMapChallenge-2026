"""Map the GEBCO surface around Iceland against lower relative sea-level datums."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import to_rgb
import numpy as np
from pyproj import Geod, Transformer
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import reproject, Resampling, transform_bounds

DAY = Path(__file__).resolve().parent
DATA = DAY / "data"  # Iceland clips of GEBCO_2026; see prepare_data.py
OUTPUT = DAY / "outputs"
CRS = "+proj=laea +lat_0=65 +lon_0=-19 +datum=WGS84 +units=m"
BOUNDS = (-345000, -230000, 345000, 225000)  # west, south, east, north, metres
FALLS = (10, 25, 50, 100)  # metres below GEBCO zero, shallowest first
ICE = ("#f6f2ce", "#b6dfd2", "#7db4b2", "#507f88")
SEA = "#192226"
PAPER = "#eef1e9"
MUTED = "#b5c4c4"
DISPLAY_CELL = 300  # metres, nearest neighbour for the map only
DIRECT = (10, 11, 12, 13, 14, 15, 16, 17)


def load_grids():
    elevation_file = DATA / "gebco_2026_iceland_elevation.tif"
    tid_file = DATA / "gebco_2026_iceland_tid.tif"
    with rasterio.open(elevation_file) as terrain, rasterio.open(tid_file) as sources:
        assert terrain.transform.almost_equals(sources.transform, precision=1e-12) and terrain.crs == sources.crs
        bounds = transform_bounds(CRS, terrain.crs, *BOUNDS, densify_pts=101)
        west, south, east, north = bounds
        window = from_bounds(west-.02, south-.02, east+.02, north+.02,
                             terrain.transform).round_offsets().round_lengths()
        elevation = terrain.read(1, window=window, masked=True)
        tid = sources.read(1, window=window)
        assert not np.ma.getmaskarray(elevation).any()
        return elevation.data, tid, terrain.window_transform(window)


def summarize(elevation, tid, transform):
    rows, cols = elevation.shape
    lon = transform.c + (np.arange(cols) + .5) * transform.a
    lat = transform.f + (np.arange(rows) + .5) * transform.e
    x, y = Transformer.from_crs("EPSG:4326", CRS, always_xy=True).transform(*np.meshgrid(lon, lat))
    west, south, east, north = BOUNDS
    submerged = (elevation < 0) & (x >= west) & (x < east) & (y >= south) & (y < north)
    # Regular longitude spacing makes ellipsoidal cell area constant along each row.
    geod = Geod(ellps="WGS84")
    areas = []
    for centre in lat:
        top, bottom = centre - transform.e / 2, centre + transform.e / 2
        area, _ = geod.polygon_area_perimeter([0, transform.a, transform.a, 0],
                                              [top, top, bottom, bottom])
        areas.append(abs(area) / 1e6)

    results = []
    provenance = []
    for fall in FALLS:
        exposed = submerged & (elevation >= -fall)
        codes, counts = np.unique(tid[exposed], return_counts=True)
        total = int(counts.sum())
        area = np.dot(exposed.sum(axis=1), areas)
        direct = counts[np.isin(codes, DIRECT)].sum()
        results.append(dict(fall_m=fall, area_km2=round(float(area), 1),
                            cells=total, direct_pct=round(100 * int(direct) / total, 2)))
        for code, count in zip(codes, counts):
            provenance.append(dict(fall_m=fall, tid=int(code), cells=int(count),
                                   cell_pct=round(100 * count / total, 3)))
    return results, provenance


def write_csv(filename, records):
    with (OUTPUT / filename).open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=records[0])
        writer.writeheader()
        writer.writerows(records)


def plot_plate(elevation, transform, results):
    west, south, east, north = BOUNDS
    width = round((east - west) / DISPLAY_CELL)
    height = round((north - south) / DISPLAY_CELL)
    grid_transform = rasterio.transform.from_bounds(*BOUNDS, width, height)
    terrain = np.empty((height, width), dtype=np.int16)
    reproject(elevation, terrain, src_transform=transform, src_crs="EPSG:4326",
              dst_transform=grid_transform, dst_crs=CRS, resampling=Resampling.nearest)
    land = terrain >= 0
    # Restrained directional relief gives the continuous terrain context.
    dy, dx = np.gradient(terrain.astype(float), DISPLAY_CELL)
    shade = np.clip(dx - dy, -.35, .35)
    sea_tone = np.clip((terrain + 1500) / 1500, 0, 1) * .030
    rgb = np.array(to_rgb(SEA)) + (sea_tone + .09 * shade)[:, :, None]
    rgb[land] = np.array(to_rgb("#656b69")) + .31 * shade[land, None]
    for fall, colour in reversed(list(zip(FALLS, ICE, strict=True))):
        rgb[(terrain >= -fall) & ~land] = to_rgb(colour)

    font = next((DAY.parent / "OTF").glob("*-Buch.otf"), None)
    if font:
        font_manager.fontManager.addfont(font)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=font).get_name()
    fig = plt.figure(figsize=(13, 8.2), facecolor=SEA)
    panel = fig.add_axes([.062, .20, .635, .60], anchor="W")
    extent = (west, east, south, north)
    panel.imshow(rgb, extent=extent, interpolation="nearest")
    panel.contour(land, levels=[.5], extent=extent, origin="upper",
                  linewidths=.24, colors="#f7f7e8")
    panel.set_axis_off()
    panel.text(-14000, 5000, "I C E L A N D", ha="center", color=PAPER, fontsize=13)
    panel.plot([west+18000, west+118000], [south+21000]*2, color=MUTED, lw=1)
    panel.text(west+18000, south+29000, "100 km", color=MUTED, fontsize=9)
    left = panel.get_position().x0
    def label(x, y, string, size, color=PAPER, **kwargs):
        fig.text(x, y, string, fontsize=size, color=color, **kwargs)

    label(left, .944, "DAY 18    /    NULL", 11, ICE[1])
    label(left, .868, "Emergent coastline", 38)
    label(.94, .944, "ICELAND     /     NORTH ATLANTIC", 10, MUTED, ha="right")
    label(left, .818, "Which parts of Iceland’s shelf would stand above a lower sea level?", 14)
    side = .683
    label(side, .765, "Hypothetical sea-level fall", 15)
    label(side, .728, "Depth below present", 10, MUTED)
    label(.94, .728, "Exposed at datum", 10, MUTED, ha="right")
    prior = 0
    for index, (row, colour) in enumerate(zip(results, ICE)):
        fall = row["fall_m"]
        baseline = .662 - index * .087
        fig.add_artist(plt.Rectangle((side, baseline-.002), .008, .031,
                                     transform=fig.transFigure, color=colour, lw=0))
        label(side+.018, baseline, f"{prior}–{fall} m", 14)
        label(.94, baseline, f"{round(row['area_km2'], -1):,.0f} km²", 14, ha="right")
        prior = fall
    label(side, .308, "Each deeper datum includes\nall shallower bands.", 11, MUTED, linespacing=1.12)
    label(side, .233, "Fine line   /   present 0 m shore", 10, PAPER)
    fig.add_artist(plt.Line2D([left, .94], [.176, .176], transform=fig.transFigure,
                              color="#556466", lw=.65))
    label(left, .132, "Present-day GEBCO terrain classified against hypothetical lower datums. Each scenario reveals currently submerged terrain.", 11)
    label(left, .098, "These static thresholds do not forecast Iceland’s coastline. Mixed sources and vertical datums limit nearshore precision.", 10, MUTED)
    label(left, .047, "#30DayMapChallenge2026 · Jane Wang · janewyx11@gmail.com", 10, MUTED)
    label(.94, .047, "GEBCO Bathymetric Compilation Group 2026  ·  15 arc-seconds", 9, MUTED, ha="right")
    fig.savefig(OUTPUT / "emergent_coastline.png", dpi=300)
    fig.savefig(OUTPUT / "emergent_coastline.svg", dpi=230)
    plt.close(fig)


if __name__ == "__main__":
    elevation, tid, transform = load_grids()
    results, provenance = summarize(elevation, tid, transform)
    OUTPUT.mkdir(exist_ok=True)
    write_csv("scenarios.csv", results)
    write_csv("provenance.csv", provenance)
    print(*results, sep="\n")
    plot_plate(elevation, transform, results)
