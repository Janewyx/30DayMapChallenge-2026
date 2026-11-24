"""Helpers for the Homeward plate: OpenStreetMap basemap, site values and glow marks."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from shapely import STRtree
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box
from shapely.ops import linemerge, polygonize, unary_union


# Overpass API ---------------------------------------------------------------

def overpass_queries(bbox, road_classes, timeout_s):
    """Return the three Overpass QL queries (roads, coastline, inland water) for one box."""
    s, w, n, e = bbox
    area = f"({s},{w},{n},{e})"
    head = f"[out:json][timeout:{timeout_s}];"
    classes = "|".join(road_classes)
    return {
        "roads": f'{head}way["highway"~"^({classes})$"]{area};out geom;',
        "coastline": f'{head}way["natural"="coastline"]{area};out geom;',
        "water": (
            f'{head}(way["natural"="water"]{area};relation["natural"="water"]{area};'
            f'way["waterway"="riverbank"]{area};relation["waterway"="riverbank"]{area};);out geom;'
        ),
    }


def cached_overpass(query, path, endpoints, timeout_s, retries, backoff_s):
    """Read a cached Overpass response, or download and cache it once.

    Each endpoint is tried with exponential backoff, since the public servers
    return 502/504 when their queues are full.
    """
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        body = urllib.parse.urlencode({"data": query}).encode()
        payload = None
        for endpoint in endpoints:
            wait = backoff_s
            for attempt in range(retries):
                try:
                    request = urllib.request.Request(endpoint, data=body, headers={"User-Agent": "python-map-render/1.0"})
                    with urllib.request.urlopen(request, timeout=timeout_s + 30) as response:
                        payload = response.read()
                    break
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
                    print(f"{endpoint} attempt {attempt + 1}: {error}; waiting {wait} s")
                    time.sleep(wait)
                    wait *= 2
            if payload is not None:
                break
        if payload is None:
            raise RuntimeError(f"Overpass download failed for {path.name}")
        path.write_bytes(payload)
        print(f"Downloaded {path.name} ({path.stat().st_size / 1e6:.1f} MB)")
    return json.loads(path.read_text())["elements"]


# OSM geometry -----------------------------------------------------------------

def project_coords(coords, transformer):
    """Project a list of {'lat','lon'} dictionaries to display x, y arrays."""
    lon = [c["lon"] for c in coords]
    lat = [c["lat"] for c in coords]
    return np.column_stack(transformer.transform(lon, lat))


def way_lines(elements, transformer):
    """Turn Overpass ways into a table of tags and projected LineStrings."""
    rows = []
    for element in elements:
        if element["type"] != "way" or len(element.get("geometry", [])) < 2:
            continue
        tags = element.get("tags", {})
        rows.append({
            "highway": tags.get("highway"),
            "name": tags.get("name"),
            "geometry": LineString(project_coords(element["geometry"], transformer)),
        })
    return pd.DataFrame(rows)


def water_polygons(elements, transformer):
    """Assemble inland water polygons from closed ways and multipolygon relations."""
    polygons = []
    for element in elements:
        if element["type"] == "way" and len(element.get("geometry", [])) >= 4:
            ring = project_coords(element["geometry"], transformer)
            if np.allclose(ring[0], ring[-1]):
                polygons.append(Polygon(ring))
        elif element["type"] == "relation":
            rings = {"outer": [], "inner": []}
            for member in element.get("members", []):
                if member.get("type") == "way" and len(member.get("geometry", [])) >= 2:
                    role = "inner" if member.get("role") == "inner" else "outer"
                    rings[role].append(LineString(project_coords(member["geometry"], transformer)))
            outer = unary_union(list(polygonize(linemerge(rings["outer"])))) if rings["outer"] else None
            if outer is None or outer.is_empty:
                continue
            if rings["inner"]:
                outer = outer.difference(unary_union(list(polygonize(linemerge(rings["inner"])))))
            polygons.append(outer)
    return unary_union([p.buffer(0) for p in polygons])


def land_from_coastline(coast_lines, frame):
    """Split a rectangular frame along OSM coastline ways and keep the land faces.

    OSM draws coastline ways with land on the left. Each face of the split frame is
    classified by sampling points just left (land) and right (water) of every coastline
    segment and taking the majority vote.
    """
    clipped = [line.intersection(frame) for line in coast_lines]
    clipped = [g for g in clipped if not g.is_empty]
    noded = unary_union(clipped + [frame.boundary])
    faces = list(polygonize(noded))
    tree = STRtree(faces)
    votes = np.zeros(len(faces))
    offset_m = 4.0  # small sideways step from the shoreline, metres

    for line in coast_lines:
        xy = np.asarray(line.coords)
        mid = (xy[1:] + xy[:-1]) / 2
        step = xy[1:] - xy[:-1]
        length = np.hypot(step[:, 0], step[:, 1])
        keep = length > 2 * offset_m
        left = np.column_stack([-step[keep, 1], step[keep, 0]]) / length[keep, None]
        for side, sign in ((mid[keep] + offset_m * left, 1), (mid[keep] - offset_m * left, -1)):
            for x, y in side:
                hits = tree.query(Point(x, y), predicate="within")
                if len(hits):
                    votes[hits[0]] += sign

    return unary_union([face for face, vote in zip(faces, votes) if vote >= 0])


def street_crossing(roads, name_a, name_b):
    """Return the point where two named OSM streets meet."""
    a = unary_union(roads.loc[roads.name.eq(name_a), "geometry"].tolist())
    b = unary_union(roads.loc[roads.name.eq(name_b), "geometry"].tolist())
    crossing = a.intersection(b)
    if crossing.is_empty:
        raise ValueError(f"{name_a} and {name_b} do not meet in the OSM cache")
    return crossing.centroid


# Measured sites ---------------------------------------------------------------

def site_values(site_hours, local_start, statistic):
    """Summarise each site's counts in the selected clock hour across its survey dates."""
    hour = site_hours.loc[site_hours.local_start.eq(local_start)]
    return (
        hour.groupby("physical_id")
        .agg(
            vehicles=("count", statistic),
            survey_days=("survey_date", "nunique"),
            first_date=("survey_date", "min"),
            last_date=("survey_date", "max"),
            source=("source", "first"),
            site_type=("site_type", "first"),
            local_area=("local_area", "first"),
            longitude=("longitude", "first"),
            latitude=("latitude", "first"),
        )
        .reset_index()
    )


def city_point(intersections, xstreet):
    """Look up a City of Vancouver intersection point by its cross-street label."""
    for feature in intersections["features"]:
        if feature["properties"]["xstreet"] == xstreet:
            return feature["geometry"]["coordinates"]
    raise KeyError(xstreet)


# Drawing ----------------------------------------------------------------------

def register_fonts(otf_dir, family="Söhne"):
    """Register the repository's Söhne files; return the family name or the fallback."""
    for font in Path(otf_dir).glob("*.otf"):
        font_manager.fontManager.addfont(font)
    if family in {f.name for f in font_manager.fontManager.ttflist}:
        return family
    print("Söhne not found in OTF/; using DejaVu Sans.")
    return "DejaVu Sans"


def font_file(otf_dir, style):
    """Path to one Söhne cut (Leicht, Buch, BuchKursiv, Kräftig), or None when absent."""
    path = Path(otf_dir) / f"Söhne-{style}.otf"
    return path if path.exists() else None


def font(fonts, family, style, size):
    """FontProperties for one Söhne cut, or the fallback family at the same size."""
    path = fonts[style]
    return FontProperties(fname=path, size=size) if path else FontProperties(family=family, size=size)


def spaced(text, gap=" "):
    """Letter-space a caps label with thin spaces (Matplotlib has no tracking setting)."""
    return "\n".join(gap.join(line) for line in text.split("\n"))


def halo_steps(core, glow):
    """Diameters or widths for the halo strokes, from the core outwards."""
    return np.geomspace(core * 1.4, core * glow["halo_scale"], glow["layers"])


def glow_points(ax, x, y, diameters_pt, glow, colours, zorder):
    """Draw soft halos plus a bright core for point sites (diameters in points)."""
    for scale in halo_steps(1.0, glow):
        ax.scatter(x, y, s=(diameters_pt * scale) ** 2, color=colours["glow"],
                   alpha=glow["halo_alpha"], linewidths=0, zorder=zorder)
    ax.scatter(x, y, s=diameters_pt ** 2, color=colours["glow"], alpha=0.9, linewidths=0, zorder=zorder + 1)
    ax.scatter(x, y, s=(diameters_pt * 0.45) ** 2, color=colours["core"], linewidths=0, zorder=zorder + 2)


def glow_line(ax, geometry, width_pt, glow, colours, zorder):
    """Draw soft halos plus a bright core along a bridge deck (width in points)."""
    lines = geometry.geoms if isinstance(geometry, MultiLineString) else [geometry]
    strokes = [(w, glow["halo_alpha"], colours["glow"]) for w in halo_steps(width_pt, glow)[::-1]]
    strokes += [(width_pt, 0.9, colours["glow"]), (width_pt * 0.4, 1.0, colours["core"])]
    for line in lines:
        x, y = line.xy
        for offset, (width, alpha, colour) in enumerate(strokes):
            ax.plot(x, y, lw=width, color=colour, alpha=alpha, solid_capstyle="round",
                    solid_joinstyle="round", zorder=zorder + offset * 0.01)


def plot_polygons(ax, geometry, **style):
    """Fill a Polygon or MultiPolygon with Matplotlib patches, keeping holes."""
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MplPath

    polygons = getattr(geometry, "geoms", [geometry])
    for polygon in polygons:
        if polygon.is_empty or polygon.geom_type != "Polygon":
            continue
        rings = [np.asarray(polygon.exterior.coords)] + [np.asarray(r.coords) for r in polygon.interiors]
        vertices = np.concatenate(rings)
        codes = np.concatenate([
            [MplPath.MOVETO] + [MplPath.LINETO] * (len(r) - 2) + [MplPath.CLOSEPOLY] for r in rings
        ])
        ax.add_patch(PathPatch(MplPath(vertices, codes), **style))


def frame_from_centre(transformer, centre_lon, centre_lat, width_m, aspect):
    """Rectangle in display coordinates centred on a lon/lat, with height = width / aspect."""
    cx, cy = transformer.transform(centre_lon, centre_lat)
    half_w, half_h = width_m / 2, width_m / aspect / 2
    return box(cx - half_w, cy - half_h, cx + half_w, cy + half_h), (cx, cy)
