"""Reconstruct the source snapshot. Set WCVP_ZIP to reuse a local v16 archive."""
import csv
import hashlib
import io
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data/raw"
ZEN = "https://zenodo.org/records/13166796/files/"
GIT = "https://raw.githubusercontent.com/"
SMALL = {
    "parfumo.csv": GIT + "rfordatascience/tidytuesday/d0536f3c1433c4eff75f9b050108232011c451a7/data/2024/2024-12-10/parfumo_data_clean.csv",
    "materials.csv": GIT + "Scento-com/perfume-dataset/58da85556a4bb42a7d56279d66fbec4dbf42cc4a/materials.csv",
    "houses.csv": GIT + "Scento-com/perfume-dataset/58da85556a4bb42a7d56279d66fbec4dbf42cc4a/houses.csv",
    "brands.csv": GIT + "parfica/parfica-open-data/c88db557698607bfbfa52d9db20c6041a10c8906/data/brands.csv",
    "tree_record.json": "https://zenodo.org/api/records/13166796",
    "tree_metadata.xlsx": ZEN + "EcoregionsTreeFinder_metadata.xlsx",
}
WCVP = "https://sftp.kew.org/pub/data-repositories/WCVP/wcvp.zip"


def digest(path, algorithm="sha256"):
    with path.open("rb") as f:
        return hashlib.file_digest(f, algorithm).hexdigest()


def stable_digest(path):
    # APIs include timing and traffic counters that change between identical lookups.
    if path.name.startswith("gbif_"):
        reply = json.loads(path.read_text())
        value = [reply["usage"], reply.get("synonym"), reply["diagnostics"]["matchType"],
                 reply["diagnostics"]["confidence"]]
    elif path.name == "tree_record.json":
        reply = json.loads(path.read_text())
        value = [reply["doi"], reply["metadata"]["license"],
                 sorted((f["key"], f["checksum"]) for f in reply["files"])]
    else:
        return digest(path)
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def fetch(url, path):
    if not path.exists():
        tmp = path.with_suffix(path.suffix + ".part")
        subprocess.run(["curl", "-fLsS", "--retry", "3", url, "-o", str(tmp)], check=True)
        tmp.replace(path)


def read(path):
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def subset(stream, output, keep):
    reader = csv.DictReader(stream, delimiter="|")
    with output.open("w", newline="") as f:
        writer = csv.DictWriter(f, reader.fieldnames)
        writer.writeheader()
        writer.writerows(row for row in reader if keep(row))


def main():
    RAW.mkdir(exist_ok=True, parents=True)
    for name, url in SMALL.items():
        fetch(url, RAW / name)
    checklist = {r["scientific_name"] for r in read(ROOT / "data/identity.csv")}
    retained = {r["scientific_name"] for r in read(ROOT / "data/selection.csv")}
    with tempfile.TemporaryDirectory() as folder:
        tmp = Path(folder)
        archive = Path(os.environ.get("WCVP_ZIP", tmp / "wcvp.zip"))
        fetch(WCVP, archive)
        if digest(archive) != "d32ea2b3a85e489b14e83bcc9eae7274532e1d113753f7be290d4b2dfde573fa":
            raise ValueError("Expected WCVP v16 (June 2026). Supply that release via WCVP_ZIP.")
        with zipfile.ZipFile(archive) as z:
            with z.open("wcvp_names.csv") as f:
                subset(io.TextIOWrapper(f, encoding="utf-8-sig"), RAW / "names.csv",
                       lambda r: r["taxon_name"] in checklist and r["taxon_status"] == "Accepted" and r["taxon_rank"] == "Species")
            ids = {r["plant_name_id"] for r in read(RAW / "names.csv") if r["taxon_name"] in retained}
            with z.open("wcvp_distribution.csv") as f:
                subset(io.TextIOWrapper(f, encoding="utf-8-sig"), RAW / "ranges.csv", lambda r: r["plant_name_id"] in ids)
        files = {f["key"]: f["checksum"] for f in json.loads((RAW / "tree_record.json").read_text())["files"]}
        def tree_subset(suffix, filename, keep):
            name = "EcoregionsTreeFinder" + suffix + ".txt"
            path = tmp / name
            fetch(ZEN + name, path)
            if "md5:" + digest(path, "md5") != files[name]:
                raise ValueError("Zenodo checksum mismatch for " + name)
            with path.open(encoding="utf-8-sig") as f:
                subset(f, RAW / filename, keep)
        tree_subset("_species", "tree_species.csv", lambda r: r["WCVP_ID"] in ids)
        species = {r["species"] for r in read(RAW / "tree_species.csv")}
        tree_subset("", "tree_pairs.csv", lambda r: r["species"] in species)
        ecos = {r["ECO_ID"] for r in read(RAW / "tree_pairs.csv")}
        tree_subset("_ecoregions", "ecoregions.csv", lambda r: r["ECO_ID"] in ecos)
    for name in sorted(retained):
        url = "https://api.gbif.org/v2/species/match?" + urlencode({"scientificName": name, "kingdom": "Plantae"})
        fetch(url, RAW / ("gbif_" + name.replace(" ", "_") + ".json"))


if __name__ == "__main__":
    main()
