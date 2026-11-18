"""Clip the Iceland window from the global GEBCO_2026 GeoTIFF downloads into data/.

One-off step: the committed clips in data/ are all emergent_coastline.py needs.
Rerun only to widen the box. Download the GeoTIFF versions of the GEBCO_2026 grid
and the GEBCO_2026 TID grid from https://www.gebco.net/data-products-gridded-bathymetry-data/gebco2026-grid,
unzip both into one folder (as gebco_2026_geotiff/ and gebco_2026_tid_geotiff/), then run

    .venv/bin/python prepare_data.py /path/to/that/folder
"""
import sys
from pathlib import Path

import rasterio
from rasterio.windows import from_bounds

DAY = Path(__file__).resolve().parent
TILE = "n90.0_s0.0_w-90.0_e0.0_geotiff.tif"
BOX = (-27.5, 62.5, -10.5, 67.5)  # west, south, east, north, degrees; covers BOUNDS with ~0.5° margin

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    downloads = Path(sys.argv[1])
    # Output clip written to data/  <-  full GEBCO tile it is cut from
    clips = {
        "gebco_2026_iceland_elevation.tif": downloads / "gebco_2026_geotiff" / f"gebco_2026_{TILE}",
        "gebco_2026_iceland_tid.tif": downloads / "gebco_2026_tid_geotiff" / f"gebco_2026_tid_{TILE}",
    }
    (DAY / "data").mkdir(exist_ok=True)
    for clip_name, tile_path in clips.items():
        with rasterio.open(tile_path) as src:
            # Whole-cell window on the source grid, so clip cells align exactly with the tile.
            window = from_bounds(*BOX, src.transform).round_offsets().round_lengths()
            profile = src.profile | dict(
                width=int(window.width), height=int(window.height),
                transform=src.window_transform(window), compress="deflate",
                predictor=2, tiled=True, blockxsize=256, blockysize=256)
            with rasterio.open(DAY / "data" / clip_name, "w", **profile) as dst:
                dst.write(src.read(window=window))
                dst.update_tags(source=tile_path.name, clip_box=str(BOX))
        print(clip_name, (DAY / "data" / clip_name).stat().st_size // 1024, "KB")
