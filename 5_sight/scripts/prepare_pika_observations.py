"""Combine source-specific observations for review, preserving their meanings.

Run with the four original data files in data/ as listed in README.md.
An optional --bodie-csv path accepts a CSV exported from the Occupancy data sheet.
"""

from pathlib import Path
import argparse
import pandas as pd

DAY = Path(__file__).resolve().parents[1]
DATA = DAY / "data"
OUTPUT = DAY / "published" / "pika_observations_combined.csv"

parser = argparse.ArgumentParser()
parser.add_argument("--bodie-csv", type=Path)
args = parser.parse_args()

ordinal_path = next(DATA.glob("doi_10_5061_dryad_z612jm6n0*/Pika_Patch-level*.csv"))
nm = pd.read_csv(ordinal_path).drop(columns=["Unnamed: 11", "Unnamed: 12"], errors="ignore")
nm = nm.rename(columns={"siteName": "site_id", "surveyYear": "year", "lastSurveyDate": "date",
                        "ordinalStatus": "source_status", "sub-region": "region"})
nm["dataset"] = "New Mexico ordinal survey"
nm["observation_type"] = "ordinal evidence status"

banff = pd.read_csv(DATA / "banff_np_tundra_pikas_2011-2023_data.csv", encoding="cp1252", skiprows=[1])
banff = banff.rename(columns={"location": "site_id", "observation_date": "date",
                              "UTM_11U_x": "easting", "UTM_11U_y": "northing"})
banff["year"] = pd.to_datetime(banff["date"], errors="coerce").dt.year
banff["dataset"] = "Banff pika haypile surveys"
banff["observation_type"] = "visit: sighting, hearing and haypile signs"
banff["coordinate_note"] = "Released UTM 11U; datum undocumented"

glacier = pd.read_csv(DATA / "glacier_np_tundra_pika_2023-2025.csv", encoding="utf-8-sig", skiprows=[1])
glacier = glacier.rename(columns={"Point.ID": "point_id", "site_name": "region", "Visit.Number": "visit_number",
                                  "elevation": "elevation_m", "Pika.sum": "pika_count", "Easting": "easting", "Northing": "northing"})
glacier["site_id"] = glacier["region"].astype(str) + " / " + glacier["point_id"].astype(str)
glacier["year"] = pd.to_datetime(glacier["date"], errors="coerce").dt.year
glacier["dataset"] = "Glacier pika point counts"
glacier["observation_type"] = "point count visit"
glacier["coordinate_note"] = "Released UTM coordinates; zone and datum undocumented"

if args.bodie_csv:
    bodie = pd.read_csv(args.bodie_csv)
else:
    workbook = next(DATA.glob("doi_10_5061_dryad_51c59zwbd*/Klingler*BODIE_CENSUS*.xlsx"))
    bodie = pd.read_excel(workbook, sheet_name="Occupancy data")
bodie.columns = bodie.columns.map(str)
years = [c for c in bodie.columns if c.isdigit() and len(c) == 4]
bodie = bodie.melt(id_vars=["Patch #", "Easting", "Northing", "Elevation (m)"],
                   value_vars=years, var_name="year", value_name="source_status")
bodie = bodie.rename(columns={"Patch #": "site_id", "Easting": "easting", "Northing": "northing", "Elevation (m)": "elevation_m"})
bodie["dataset"] = "Bodie Hills occupancy census"
bodie["observation_type"] = "patch census occupancy"
bodie["coordinate_note"] = "Released UTM zone 11S label; datum undocumented"

# Keep dataset-specific columns: zero, unknown, and old sign are not interchangeable.
combined = pd.concat([nm, banff, glacier, bodie], ignore_index=True, sort=False)
first = ["dataset", "observation_type", "site_id", "date", "year", "source_status", "latitude", "longitude", "easting", "northing", "coordinate_note", "elevation_m"]
combined = combined[first + [c for c in combined.columns if c not in first]]
OUTPUT.parent.mkdir(exist_ok=True)
combined.to_csv(OUTPUT, index=False)
print(combined.groupby("dataset").size().to_string())
print(f"Saved {OUTPUT}")
