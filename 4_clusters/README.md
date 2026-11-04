# Day 04 — Clusters: Trader Joe's

This folder contains a reproducible notebook comparing observed store points, HDBSCAN clusters, and Gaussian KDE surfaces across the contiguous United States.

## Run

From `4_clusters/`:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m ipykernel install --prefix .venv --name python3
.venv/bin/python build_notebook.py
JUPYTER_PATH=.venv/share/jupyter MPLCONFIGDIR=.mplconfig \
  .venv/bin/python execute_notebook.py
```

The notebook reads the CartoDB raster URL from `../secrets/readme` without printing or embedding it. If tiles are unavailable, maps fall back to the local Census state boundaries. The state boundary archive is the U.S. Census Bureau's 2025 1:20,000,000 cartographic boundary file.

Outputs are written to `outputs/` at 300 DPI.
