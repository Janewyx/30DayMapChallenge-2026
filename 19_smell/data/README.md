# Day 19 · Data, provenance and the wider feasibility study

The [main README](../README.md) describes the submitted plate. This file keeps the background: how the inputs were acquired, how well the note dictionary covers the corpus, the full species review, and the brand-origin question this study started from. Links below are relative to the day folder.

## Original question and feasibility finding

Do perfume brands describe their fragrances with notes associated with plants native to the brand’s founding country or ecoregion?

**Feasibility finding.** Eight identifiable plants appear in 9,265 perfumes from 1,165 brands. All eight have Kew native distributions. TreeFinder supplies expected-native ecoregions for all seven woody species. The limiting evidence is where the brands began. Of the 1,165 brands, 231 have a single reported country across the two dictionaries, one has conflicting countries, and 933 lack a country in both. Three house histories verify founding countries for a pilot covering 290 perfumes. These data support a descriptive pilot. A claim of disproportionate use needs a larger verified brand sample and a comparison baseline.

## Acquiring the inputs

To reconstruct the inputs, run `.venv/bin/python acquire.py` before the build. It uses curl, pinned GitHub revisions and a checksum for WCVP v16. Kew’s per-species endpoint returned HTTP 403 during acquisition. The script filters Kew’s names and distribution tables locally. TreeFinder provides versioned, pipe-delimited files without a row-filtering download endpoint. Only the species, relationship and ecoregion records needed for the selected candidates persist. The bulk downloads are temporary. If Kew advances its live archive, supply the v16 ZIP with `WCVP_ZIP=/path/to/wcvp.zip`. GBIF queries are cached individually. The manifest records original file hashes and stable-content hashes for API replies with variable diagnostics or counters. A changed taxonomic match requires review. [Source manifest](sources.json) · [Kew v16 archive](https://doi.org/10.34885/egs6-cp24)

To inspect coverage with the pinned Python environment:

```sh
.venv/bin/python - <<'PY'
import duckdb
from pathlib import Path
with duckdb.connect("outputs/perfume.duckdb", read_only=True) as db:
    for statement in db.extract_statements(Path("sql/feasibility.sql").read_text()):
        db.sql(statement.query).show()
PY
```

## Perfumes and dictionary coverage

The TidyTuesday file contains 59,325 records and 59,281 distinct perfume URLs. `Number` is a text field with leading zeroes and missing values. A hash of the URL identifies a perfume. `perfume_source` retains every input row’s original number, descriptive fields and note strings. `perfume` chooses a representative row for each URL, preferring known year and perfumer. `perfume_note` combines the evidence from all rows for that URL, retaining one mention per normalized note and pyramid position, the original label, source row, ordinality, brand, year and perfumer. A perfume can contribute at each position, and counts across taxa can overlap. Only 31,163 perfumes have any pyramid notes. The other perfumes have unknown note use.

The 318,393 position-level mentions yield 3,998 distinct written labels and 3,997 normalized keys. Normalization folds case and accents and collapses punctuation and whitespace. Scento has 420 material records with columns `id, name, aliases, material_family, origin, smell, url`. Aliases are semicolon-delimited. Of the materials, 165 are natural, 190 accords, 32 synthetic, 15 both, and 18 unspecified. These are material descriptions. A perfume’s declared note describes an impression and does not establish ingredient chemistry, harvest location or trade route.

| Scento match | Distinct note keys | Position-level mentions |
| --- | ---: | ---: |
| Material name | 317 | 237,785 |
| Alias only | 220 | 40,702 |
| Unmatched | 3,460 | 39,906 |

Exact names and aliases reach **13.4% of the vocabulary and 87.5% of mentions**. Exact names take priority in the summary. The match bridge retains every matching dictionary label and its method. The raw spelling inventory is in `raw_note_frequency.parquet`. [Corpus SQL](../sql/corpus.sql)

## From a note to a plant

After automatic matching across the whole corpus, a small reviewed list links specific note wordings to candidate binomials. Each surviving rule requires a unique matching material, a natural or mixed origin, and an exact accepted species in WCVP. The rule identifies a botanical referent. Natural materials of animal origin and abstract accords have no eligible species rule. The unmatched tuberose proposal remains in the review input and contributes no taxon. The ranked result contains 27 note–species pairs across 26 Scento materials. It is a frequency ranking within the reviewed vocabulary, so its counts are conservative lower bounds. A spelling or alias outside the reviewed rule contributes no perfumes to that species.

For example, Scento places both Virginia cedar and Atlas cedar under cedarwood. Only those specific labels enter their respective species counts. Generic cedar, cedarwood, sandalwood and pine remain available in the note inventory for inspection. The shortlist prioritizes woods, resins and tree-derived floral, spice and leaf materials. Selection also considers brand breadth, geographic contrast and availability of native-range evidence. Vetiver provides a frequent non-tree comparison. [Identity rules](identity.csv) · [Selection reasons](selection.csv) · [Botanical SQL](../sql/botany.sql)

The Kew bridge retains area codes, names and all three original status flags. The strict native subset retains 103 species–area rows with introduced, extinct and location-doubtful flags all zero. TreeFinder’s 2024 species index links through WCVP identifiers and preserves its source names and WFO IDs. Of 570 observed species–ecoregion pairs, 182 have positive reported ecoregion overlap with the native range. These are expected-native relationships. The source uses broad native areas and buffered ecoregions, so a positive overlap does not demonstrate nativeness throughout a polygon. GBIF returned eight exact species matches as supplementary identifiers. The grass lies outside TreeFinder’s scope. [TreeFinder methods](https://doi.org/10.1111/geb.70064)

## Brand geography and analytical limits

Scento’s 160 houses have fields `id, name, country, founded, type, portrait, perfume_count, url`. Country is populated for 158. Normalized exact name joins supply a country for 130 of 1,451 named corpus brands. Parfica’s Wikidata-linked table raises the union to 261. It combines country (P17) and country of origin (P495). The country field alone cannot establish founding location. The two references disagree on Nasomatto, Orto Parisi and Escentric Molecules. All source claims remain in `brand_origin`, with named conflicts in `brand_country_review`. The pilot’s three verified records live separately in `brand_founding`, with primary-source URLs. Perfumer credits remain verbatim in the perfume tables. [Parfica provenance](https://github.com/parfica/parfica-open-data) · [Founding evidence](founding.csv)

For a later hypothesis test, define the population as perfumes with reported pyramid notes and verified house origins. Compare each house’s local-species use with an expectation that preserves species popularity and house portfolio sizes, for example by permuting country labels among comparable houses and checking sensitivity to release period. Count a species once per perfume and account for clustering by house. WCVP level-3 botanical areas sometimes split or cross sovereign boundaries. A documented political-country crosswalk is needed for country comparisons. Ecoregion membership requires a documented founding locality with enough precision to assign an Ecoregions 2017 polygon. A country spanning many ecoregions cannot supply that precision. Both missing note pyramids and stronger coverage of prominent houses can bias the comparison.

## Further sources

- Scento Perfume Database, materials and houses, CC BY 4.0. Parfica attributes its country and founding-year fields to Wikidata under CC0. The snapshot includes source material and house URLs and Wikidata QIDs. [Scento](https://github.com/Scento-com/perfume-dataset) · [Parfica](https://github.com/parfica/parfica-open-data)
- Govaerts, R., ed. (2026). World Checklist of Vascular Plants v16, Royal Botanic Gardens, Kew, CC BY 3.0. Taxa retain WCVP plant-name IDs, IPNI identifiers and POWO URLs. [WCVP release](https://doi.org/10.34885/egs6-cp24)
- Kindt, R. (2024). EcoregionsTreeFinder 2024.08, CC BY 4.0. The archive includes its field dictionary and per-file checksums. The retained ECO_ID is the join key for later global Ecoregions 2017 polygons. [Zenodo release](https://zenodo.org/records/13166796)
- GBIF species-match API v2 supplies a usage key, rank, status and match diagnostics. Occurrence datasets carry publisher-specific licences. This phase downloaded no occurrence records or spatial polygons. [GBIF species API](https://techdocs.gbif.org/en/openapi/v1/species) · [GBIF data use](https://techdocs.gbif.org/en/data-use/)
