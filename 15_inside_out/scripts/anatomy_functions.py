"""Rendering engine for the Findelen "taken apart" exploded-layer plate.

Each of the three layers (ice surface, nunataks, subglacial bed) is drawn the same
way: resample for smooth shading, shade under a few lights, project through one
fixed orthographic camera, then splat into a shared canvas depth-first (farthest
pixels drawn first, nearest last, so near terrain correctly covers far terrain).
Only the *data* each layer draws from differs — the camera and render path are
identical, which is what keeps the three layers visually comparable.

Layout and figure/caption drawing stay in the notebook, since that's the part
meant to be tweaked by eye. This module holds the reusable math.
"""
from pathlib import Path
import numpy as np
import rasterio
from scipy import ndimage
from PIL import Image
from matplotlib.colors import LinearSegmentedColormap


def load_grids(data_dir):
    """Read the three same-grid 25 m ASCII rasters: surface, bed, ice thickness."""
    def read(name):
        with rasterio.open(Path(data_dir) / name) as ds:
            return ds.read(1).astype(float), ds.res[0]
    surface, cell = read('dhm_fin2016.asc')
    bed, _ = read('bedrock_fin2016.asc')
    thickness, _ = read('ice_thickness_fin2016.asc')
    return surface, bed, thickness, cell


def crop_to_footprint(surface, bed, thickness, cell, rock_margin_m):
    """Trim every grid to the ice plus a rounded rock margin; split rock vs. ice."""
    ice = thickness > 0.1
    dist = ndimage.distance_transform_edt(~ice)
    footprint = ndimage.gaussian_filter((dist <= rock_margin_m / cell).astype(float), 2.5) > .5
    rows, cols = np.where(footprint)
    crop = np.s_[max(rows.min() - 3, 0):rows.max() + 4, max(cols.min() - 3, 0):cols.max() + 4]
    surface, bed, ice, footprint, thickness = (a[crop] for a in (surface, bed, ice, footprint, thickness))
    rock = footprint & ~ice
    return surface, bed, ice, footprint, thickness, rock


def count_nunataks(ice, min_cells):
    """Ice-free islands fully enclosed by ice, at least `min_cells` 25 m cells each."""
    holes, _ = ndimage.label(ndimage.binary_fill_holes(ice) & ~ice)
    sizes = np.bincount(holes.ravel())[1:]
    return int((sizes >= min_cells).sum())


def resample(a, up, order=3):
    """Upsample a grid `up`x for smooth shading only — adds no real detail."""
    return ndimage.zoom(a, up, order=order, mode='nearest', grid_mode=True)


def build_camera(shape, cell, up, azimuth_deg, elevation_deg):
    """One fixed orthographic camera, shared by every layer.

    Returns, for every resampled cell:
      sx_flat   screen-right position (m)
      depth_h   horizontal distance into the scene, before the camera tilts (m)
      grid_line mask marking each native 25 m grid row (used to engrave that texture)
    """
    H, W = shape
    yy, xx = np.mgrid[0:H * up, 0:W * up].astype(np.float32)
    gx = (xx + .5) / up * cell                      # metres east
    gy = -(yy + .5) / up * cell                      # metres north
    az = np.deg2rad(azimuth_deg)
    sx_flat = gx * np.cos(az) - gy * np.sin(az)
    depth_h = gx * np.sin(az) + gy * np.cos(az)
    row_frac = ((yy + .5) / up) % 1.0
    grid_line = np.minimum(row_frac, 1 - row_frac) < .055
    return sx_flat, depth_h, grid_line


def shade(z, cell, up, relief, lights, contrast):
    """Multi-light Lambertian intensity (0-1), contrast-stretched around mid-grey."""
    dzdy, dzdx = np.gradient(z * relief, cell / up)
    dzdy = -dzdy                                      # grid rows run south
    norm = np.sqrt(1 + dzdx ** 2 + dzdy ** 2)
    out = 0
    for az, alt, w in lights:
        az, alt = np.deg2rad(az), np.deg2rad(alt)
        out = out + w * (-dzdx * np.sin(az) * np.cos(alt) - dzdy * np.cos(az) * np.cos(alt) + np.sin(alt)) / norm
    return np.clip((out - .5) * contrast + .55, 0, 1)


def project(z, z_ref, relief, depth_h, elevation_deg):
    """Tilt the camera down by `elevation_deg`: returns (screen-up, depth-into-scene)."""
    el = np.deg2rad(elevation_deg)
    zz = (z - z_ref) * relief
    return depth_h * np.sin(el) + zz * np.cos(el), depth_h * np.cos(el) - zz * np.sin(el)


def render_layer(z, mask, material, cell, up, relief, lights, sx_flat, depth_h, grid_line,
                  elevation_deg, z_ref):
    """Shade, colour and project one layer; return flat sx, sy, dep, rgb for its visible cells."""
    zf = resample(z, up)
    visible = resample(mask.astype(np.float32), up, order=1) > .5
    sy, dep = project(zf, z_ref, relief, depth_h, elevation_deg)
    inten = shade(zf, cell, up, relief, lights, material['contrast'])
    rgb = LinearSegmentedColormap.from_list('m', material['ramp'])(inten)[..., :3]
    if 'warm' in material:   # low ice (debris-covered tongue) drifts toward warm grey
        warm_w = np.clip((3300 - zf) / 700, 0, 1)[..., None] * material['warm_max']
        rgb = rgb * (1 - warm_w) + LinearSegmentedColormap.from_list('w', material['warm'])(inten)[..., :3] * warm_w
    if material['engrave'] < 1:
        rgb[grid_line] *= material['engrave']   # darken every native 25 m grid row
    return sx_flat[visible], sy[visible], dep[visible], rgb[visible].astype(np.float32)


def silhouette(sx, sy, sx0, sx1, bins=600):
    """Per-column (top, bottom) screen-y envelope of a layer's visible cells."""
    b = ((sx - sx0) / (sx1 - sx0) * (bins - 1)).astype(int)
    top = np.full(bins, -np.inf)
    bot = np.full(bins, np.inf)
    np.maximum.at(top, b, sy)
    np.minimum.at(bot, b, sy)
    return top, bot


def clearance(sil, layer_order):
    """How far each upper layer must rise so its silhouette never crosses the one below it."""
    clear = {}
    for upper, lower in zip(layer_order[:-1], layer_order[1:]):
        ok = np.isfinite(sil[upper][1]) & np.isfinite(sil[lower][0])
        clear[upper] = np.max(sil[lower][0][ok] - sil[upper][1][ok])
    return clear


def stack_lifts(layers, layer_order, clear, gap_m):
    """Vertical lift (m) for each layer so the whitespace between silhouettes is even."""
    lift, acc = {layer_order[-1]: 0.0}, 0.0
    for upper in layer_order[-2::-1]:
        acc += clear[upper] + gap_m
        lift[upper] = acc
    lo = min(layers[k]['sy'].min() + lift[k] for k in layer_order)
    hi = max(layers[k]['sy'].max() + lift[k] for k in layer_order)
    return lift, lo, hi


def splat(sx, sy, dep, rgb, dy, sx0, sy1, px_per_m, size, min_blob=400):
    """Orthographic z-buffer splat of one layer onto an RGBA canvas of `size` = (Wp, Hp)."""
    Wp, Hp = size
    order = np.argsort(-dep)                          # far first, near last
    ix = ((sx[order] - sx0) * px_per_m).astype(np.int64)
    iy = ((sy1 - sy[order] - dy) * px_per_m).astype(np.int64)
    rgb = rgb[order]
    cbuf = np.zeros((Hp * Wp, 3), np.float32)
    abuf = np.zeros(Hp * Wp, bool)
    for ox in range(3):
        for oy in range(3):
            k = (iy + oy) * Wp + (ix + ox)
            cbuf[k] = rgb
            abuf[k] = True
    lab, _ = ndimage.label(abuf.reshape(Hp, Wp))       # drop edge-on specks
    keep = np.bincount(lab.ravel()) >= min_blob
    keep[0] = False
    img = np.dstack([cbuf.reshape(Hp, Wp, 3), keep[lab]])
    return Image.fromarray((img * 255).astype(np.uint8), 'RGBA')
