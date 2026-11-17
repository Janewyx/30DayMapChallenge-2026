# Day 15 · Inside out — Findelen, taken apart

This plate shows Findelengletscher, in the Valais Alps of Switzerland, separated into three layers: the ice surface, the ice-free rock that rises through it, and the terrain beneath the ice. All three layers come from a single model of surface elevation, bed elevation and ice thickness, published by Feiger, Huss, Leinss, Sold & Farinotti (2018). Because the three grids share one 25 m spacing, the layers can be compared directly.

## Plate · Findelen, taken apart

![Findelen, taken apart](outputs/findelen_anatomy_preview.png)

Every layer is drawn with the same camera, which keeps the glacier outline aligned from one layer to the next. The layers differ only in their height on the page. Each one is raised just enough to clear the layer below it, so the spacing between them stays even.

The bed is the least certain of the three layers. It comes from radar measurements combined with modelling, rather than from direct observation of the whole glacier floor. The plate counts 15 enclosed nunataks: rock islands of at least 1,250 m² that are fully surrounded by ice.

The plate is built in a notebook, so each step can be run and inspected on its own. The steps are loading the data, checking that the grids agree, setting up the camera, shading each layer, stacking the layers, combining them into one image, and drawing the plate. Each step ends with a small working figure.

- `notebooks/findelen_anatomy.ipynb` runs the full process from top to bottom.
- `scripts/anatomy_functions.py` holds the rendering functions: resampling, shading, the camera, layer stacking and compositing.
- `scripts/anatomy_config.yaml` holds the settings for the camera, layout, type sizes and colours. To restyle the plate, edit this file rather than the code.

The notebook writes three files: `outputs/findelen_anatomy.png` (3900 × 4875 px, 300 DPI), `outputs/findelen_anatomy_preview.png` (1300 px wide) and `outputs/findelen_anatomy_metadata.json`.

## Setup with uv

The project uses its own virtual environment, managed with [uv](https://docs.astral.sh/uv/). Run the three steps below from the `15_inside_out` folder.

**1. Create the environment and install the dependencies.**

```bash
uv venv .venv
uv pip install -r requirements.txt
```

**2. Download and prepare the data.** The source grids are not stored in Git. This step downloads the published supplement (about 1.5 MB) and extracts it into `data/findelen_gries/bed_study_extracted/`. The extraction script leaves the grids unchanged. It also records the same surface, bed and thickness check that the notebook repeats in its second step.

```bash
mkdir -p data/findelen_gries
curl -L -o data/findelen_gries/bed_study_supplement.zip \
  https://gh.copernicus.org/articles/73/1/2018/gh-73-1-2018-supplement.zip
.venv/bin/python scripts/prepare_bed.py
```

**3. Render the plate.** Execute the notebook in place:

```bash
.venv/bin/python -m jupyter execute --inplace notebooks/findelen_anatomy.ipynb
```

To work in the notebook interactively, open it in VS Code or Jupyter and select `.venv` as the kernel. The notebook locates the project folder on its own, so it runs from the repository root, the day folder or the `notebooks` folder. The `.venv` folder and the downloaded data are excluded from Git.

The plate is set in Söhne, a licensed typeface that is not included in the repository. The notebook looks for it in the folder named under `fonts` in `scripts/anatomy_config.yaml`. If the font is not there, the notebook uses DejaVu Sans, which ships with matplotlib, and prints a short note. Line lengths will differ slightly in that case, because the layout was tuned for Söhne.

## Source data

The plate reads three grids, each at its native 25 m spacing. Step 2 of the setup places them in `data/findelen_gries/bed_study_extracted/`.

- `dhm_fin2016.asc`: surface elevation.
- `bedrock_fin2016.asc`: bed elevation.
- `ice_thickness_fin2016.asc`: ice thickness.

These grids come from Feiger, Huss, Leinss, Sold & Farinotti (2018), *The bedrock topography of Gries- and Findelengletscher* ([study](https://doi.org/10.5194/gh-73-1-2018), [data supplement](https://gh.copernicus.org/articles/73/1/2018/gh-73-1-2018-supplement.zip)). The publication is licensed CC BY 3.0, and the supplement's attribution and terms should be retained.

The wider dataset search for this day is documented in [`data/README.md`](data/README.md). It covers the other glaciers considered, what was downloaded and what was only catalogued, licensing and checksums, and the reasons each candidate was used or set aside.
