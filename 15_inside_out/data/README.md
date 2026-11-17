# Day 15 data collection — glacier surface and bed survey search

Question behind the search: which published survey datasets support a detailed glacier surface mesh, a defensible subglacial bed, and supporting high-resolution imagery or point clouds?

**Collection complete: 20 verified downloads, approximately 5.47 GB of source assets.** All raster headers opened successfully; Findelen survey, flight-plan and bed-supplement ZIPs passed internal CRC checks. Sources were checked on **2026-11-14**. Original downloads are preserved.

See `download_manifest.json` for completed downloads, source URLs, licences, sizes and SHA-256 checksums; publisher MD5 checksums are verified where available. `raster_inventory.json` records actual file-header resolution, CRS, dimensions and bounds. `archive_inventory.json` lists archive members without requiring large archives to be unpacked.

Only Findelen's 25 m grids (below) feed the published plate — see [`../README.md`](../README.md). Everything else here documents the wider search: what else was found, what was downloaded versus only catalogued, and why each candidate was or wasn't used.

## Findings and priority

The original recommendations mainly supplied glacier **surface** geometry. They did not establish subglacial coverage. Ordinary airborne LiDAR and optical UAV photogrammetry do not reveal the bed through glacier ice. A bare-earth DTM is not an ice-free bedrock DEM. Here, bed terrain comes from radar-constrained estimates and interpolation, with substantially coarser effective detail than the optical surface surveys.

| Priority / site | Surface | Bed / thickness | Supporting collection | Assessment |
|---|---|---|---|---|
| **1 — Findelengletscher, Switzerland** | Header-verified UAV DSM, 0.10 m; selected 2016-08-30 survey covers part of the tongue | Downloaded 25 m surface, bedrock, ice thickness and three uncertainty grids from Feiger et al. | Same-survey 0.10 m orthophoto, processing report; survey overview and flight-plan archive | Best combination in this collection. Fine surface over a coarser, radar-constrained bed; survey footprint is smaller than bed-model domain. |
| **2 — Griesgletscher, Switzerland** | Downloaded 25 m reference surface; 0.10 m UAV surveys are catalogued but not bulk-downloaded | Downloaded 25 m bedrock, thickness and uncertainty grids | Survey overview and flight plans downloaded; individual UAV URLs in EnviDat catalogue | Strong alternative for more complete glacier coverage. A high-resolution UAV survey still needs downloading. |
| **3 — Vernagtferner, Austria** | Seven downloaded/published surface DEMs, **20 m** in this release, 1969–2018 | 20 m bed raster estimated from 2006 radar measurements | Four 2022 UAV orthophotos, **3.4–4.8 cm**, and historical glacier outlines | Useful complete geometry bundle, but the published DEMs do **not** meet a ≤2 m elevation requirement. Do not mistake fine imagery for a fine DEM. |
| **4 — Belvedere, Italy** | Selected 2015 UAV DSM, **0.50 m actual header** (filename says 20 cm) | No bed supplied in this release | Same-year orthophoto, dense COPC/LAZ point cloud, survey metadata | Excellent high-resolution surface collection; incomplete for inside/out until a defensible bed source is added. |
| **5 — Kanderfirn, Switzerland** | Selected 2017-09-27 DSM, 0.25 m | No bed supplied in this release | Same-date 0.05 m orthophoto | Small elevation file for rendering experiments; orthophoto is much larger. |
| **Regional audit — Whistler/Horstman/Blackcomb** | 25 m absolute DEMs in published archive | No bed raster in downloaded archive | Glacier outlines, climate data; 5 m and ~6.43 m elevation-change rasters | Does not meet fine-surface + bed requirements. Elevation change is not absolute surface height. |
| **Inspection only — Rhône collapse feature** | Study uses photogrammetric surface data | High-density GPR study of a ~100 × 150 m area | One depth-slice animation and study page collected | Public Zenodo release is videos, **not numerical GPR volumes or bed grids**. Numerical data are available from authors on request. |

No verified ≤2 m subglacial bed product for Whistler / Fitzsimmons / Blackcomb was found. This is a finding about the releases inspected, not proof that such measurements do not exist.

Supporting high-resolution collection here means **processed orthophotos, point clouds, flight plans and processing metadata**, as provided by each publisher. It does not imply that original individual camera frames or raw GPR traces are included.

## Start with Findelen

`findelen_gries/bed_study_extracted/` contains directly usable ASCII grids:

- `dhm_fin2016.asc`: reference surface elevation.
- `bedrock_fin2016.asc`: estimated bed elevation.
- `ice_thickness_fin2016.asc`: estimated ice thickness.
- `uncertainty_GPR_fin2016.asc`, `uncertainty_ITEM_fin2016.asc`, `uncertainty_combined_fin2016.asc`: separate measurement, modelling and combined uncertainty.
- Equivalent `*_gries2016.asc` files contain Griesgletscher data.

Original archive: `findelen_gries/bed_study_supplement.zip`. Its README is retained verbatim; the combined-uncertainty paragraph contains an apparent numbering typo. The study describes combination of radar and interpolation uncertainty in quadrature.

The selected `findelen_gries/findelen_20160830.zip` contains the finer surface survey and its companion orthophoto/report. Both GeoTIFFs are **37,808 × 20,444 pixels at 0.10 m**, with EPSG:2056 embedded in their headers. The processing-report PDF is also extracted beside the ZIP for convenient inspection. Read the processing report and `datasets_overview.pdf` for coverage and quality. The EnviDat collection describes its coordinate system as **CH1903+ / LV95**. The bed ASCII grids have **no embedded CRS** and use coordinates consistent with **CH1903 / LV03** (e.g. Findelen easting ~628,000, northing ~91,000). Treat LV03 as an inference to confirm against authoritative metadata/control points, not verified file metadata. Do not overlay these coordinate values directly or simply relabel LV95 as LV03.

Before deriving thickness from the fine surface: establish horizontal and vertical datums, dates, ice mask and common coverage. The 2016 reference surface is not necessarily the exact UAV survey date. Snow/ice changes can matter even within a year. Preserve the 25 m bed grid and uncertainty; interpolation to 10 cm only supports rendering and does not create measured bed detail. The safer scientific thickness product is the published internally consistent 25 m field.

An arithmetic check of the supplied surface minus bed minus thickness produced maximum absolute residuals below **0.01 m** for both glaciers, consistent with file rounding. This checks internal consistency, not scientific accuracy; see `bed_consistency.json`.

## Additional header findings

Vernagtferner's UAV ZIP contains July and September 2022 orthophotos for **Brochkogel** and **Taschach**, at approximately 3.4–4.8 cm. Their headers specify **EPSG:25832** (ETRS89 / UTM 32N), whereas the DEMs and bed use **EPSG:32632** (WGS 84 / UTM 32N). This differs from the repository description saying all data use 32632. Preserve the actual headers and transform deliberately if combining them; do not overwrite CRS based on the landing page. These are four-band images, not elevation rasters.

Belvedere's selected 2015 DSM is **0.50 m**, 4767 × 7437 cells, despite `20cm` in its filename and a 0.2 m claim in the survey JSON. The actual DSM header uses EPSG:7791. Its companion orthophoto really is 0.20 m (9049 × 17195 pixels), with EPSG:32632 in its header; that also conflicts with the survey JSON's EPSG:7791 claim. Its point cloud has **67,997,364 points**; the COPC header says EPSG:32632 while the survey JSON says EPSG:7791. The JSON also describes point heights as **ellipsoidal** and DSM heights as **orthometric (ITALGEO05)**. Do not directly subtract point elevations from DSM elevations without resolving that vertical-datum difference. These discrepancies are preserved in the inspection record.

## Sources and attribution

- **Bed / thickness / uncertainty:** Feiger, Huss, Leinss, Sold & Farinotti (2018), *The bedrock topography of Gries- and Findelengletscher*. [Study](https://doi.org/10.5194/gh-73-1-2018), [data supplement](https://gh.copernicus.org/articles/73/1/2018/gh-73-1-2018-supplement.zip). Publication is CC BY 3.0; retain supplement attribution and accompanying terms. Bed is radar-constrained ITEM modelling, not spatially continuous direct bed measurement.
- **Findelen / Gries UAV:** Gindraux, Farinotti & Boesch (2017), [EnviDat DOI 10.16904/envidat.48](https://doi.org/10.16904/envidat.48). Catalogue declares **ODbL** (`odc-odbl`), not CC BY. [Methods](https://doi.org/10.3390/rs9020186). Original metadata saved in `catalogue/envidat_48.json`.
- **Vernagtferner:** Dobler (2026), [Zenodo 17590496](https://zenodo.org/records/17590496), CC BY 4.0. [Final study](https://doi.org/10.5194/tc-20-2531-2026). Historical bed and later surfaces are not simultaneous surveys.
- **Belvedere:** Ioli et al., [Zenodo 19265915, version 3.0](https://zenodo.org/records/19265915), CC BY 4.0. [Survey study](https://doi.org/10.3390/rs14010028). Selected 2015 files form one same-year surface collection, rather than a mixture of survey years.
- **Kanderfirn:** Groos et al. (2019), [Zenodo 2706019](https://zenodo.org/records/2706019), CC BY 4.0. [Methods](https://doi.org/10.3390/geosciences9080356).
- **Whistler:** Monty, [Zenodo 15943001](https://zenodo.org/records/15943001), CC BY 4.0. [Study](https://doi.org/10.1017/aog.2026.10045).
- **Rhône:** Ruols et al. (2025), [study](https://doi.org/10.5194/tc-19-4045-2025), [video supplement](https://zenodo.org/records/15652968), CC BY 4.0. Video is an inspection reference, not reusable numerical bed geometry.

## Other candidates retained for inspection

Full publisher catalogue JSON is saved under `catalogue/`, including file URLs, sizes, licences and descriptions. [`../CANDIDATES.md`](../CANDIDATES.md) explains what was not bulk-downloaded and why. No survey was silently advertised as a locally completed download: the manifest is authoritative.

## Reproduce / inspect

Run from the repository root:

```bash
python3 15_inside_out/scripts/download_selected.py
# Optional faster, resumable range downloads:
python3 15_inside_out/scripts/download_ranges.py
# In an environment with requirements.txt installed:
python3 15_inside_out/scripts/prepare_bed.py
python3 15_inside_out/scripts/inspect_assets.py
```

The inspection environment used during collection was temporary (`/tmp/inside-out-inspect`). Source GeoTIFFs can be opened directly in QGIS; ZIP members can be inspected using GDAL `/vsizip/`. Small bed grids have also been extracted for convenience. Large original survey ZIPs are retained without a duplicate full extraction.

For the published plate, the UAV surface is **not** used; only the 25 m surface, bed and thickness grids are. No cross-survey bed reconstruction is performed.
