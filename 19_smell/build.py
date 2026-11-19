"""Verify the cached snapshot and build the analytical database and portable tables."""
from acquire import stable_digest
import json
import os
import tempfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)


def main():
    manifest = json.loads(Path("data/sources.json").read_text())
    for record in manifest:
        path = Path("data/raw", record["file"])
        if stable_digest(path) != record["stable_sha256"]:
            raise ValueError(f"Snapshot mismatch: {path}. See README before updating sources.")
    out = Path("outputs")
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out) as stage:
        staging = Path(stage)
        con = duckdb.connect(str(staging / "perfume.duckdb"))
        for script in ["corpus", "botany"]:
            con.execute(Path("sql", script + ".sql").read_text())
        con.execute("""create table source_manifest as select * from read_json_auto('data/sources.json')""")
        checks = {
            "perfume URLs unique and present": "select count(*)=count(distinct source_url) from perfume",
            "all raw rows recoverable via ID": "select count(*)=0 from perfume_source anti join perfume using(perfume_id)",
            "note position keys unique": "select count(*)=count(distinct (perfume_id,position,note_key)) from perfume_note",
            "note counts reconcile": "select sum(top_mentions+middle_mentions+base_mentions)=(select count(*) from perfume_note) from note_frequency",
            "all selected species resolved once with native ranges": """select count(*)=(select count(*) from 'data/selection.csv')
                and count(*)=count(distinct plant_name_id) and min(native_areas)>0 from candidate_taxa""",
            "dictionary shortlist uses unambiguous matches": """select count(*)=0 from material_taxon
                join note_frequency using(note_key) where match_count!=1 or note_key in ('cedar','cedarwood','pine','sandalwood')""",
            "TreeFinder links unique": "select count(*)=count(distinct (plant_name_id,ECO_ID)) from ecoregion_tree",
            "TreeFinder links reference candidates": "select count(*)=0 from ecoregion_tree anti join candidate_taxa using(plant_name_id)",
            "candidate counts reconcile": """select count(*)=0 from candidate_taxa c join candidate_coverage v using(scientific_name)
                where c.perfumes!=v.perfumes or c.brands!=v.brands""",
        }
        for description, query in checks.items():
            if not con.execute(query).fetchone()[0]:
                raise ValueError(description)
        tables = [r[0] for r in con.sql("show tables").fetchall()]
        counts = {}
        for table in tables:
            counts[table] = con.sql(f"select count(*) from {table}").fetchone()[0]
            con.execute(f"copy {table} to '{staging}/{table}.parquet' (format parquet, compression zstd)")
            exported = con.sql(f"select count(*) from '{staging}/{table}.parquet'").fetchone()[0]
            if exported != counts[table]:
                raise ValueError(f"Parquet row count mismatch for {table}")
        for table, order in [("candidate_taxa","perfumes desc"),("botanical_shortlist","frequency_rank"),
                             ("candidate_coverage","perfumes desc"),("note_frequency","perfumes desc,note_key")]:
            con.execute(f"copy (select * from {table} order by {order}) to '{staging}/{table}.csv' (header)")
        (staging / "validation.json").write_text(json.dumps({"rows": counts, "checks_passed": list(checks)}, indent=2)+"\n")
        con.close()
        for file in staging.iterdir():
            file.replace(out / file.name)


if __name__ == "__main__":
    main()
