create table taxon as
select plant_name_id, ipni_id, powo_id, taxon_name scientific_name, taxon_authors, taxon_status, taxon_rank,
       family, geographic_area, lifeform_description,
       'https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:'||powo_id source_url
from read_csv('data/raw/names.csv', all_varchar=true);
-- The original label is part of this bridge's key. A generic material ID alone is insufficient.
create table material_taxon as
select distinct m.id material_id, f.note_key, t.plant_name_id, m.material_family,
       'reviewed note wording + exact WCVP accepted species' match_method,
       'species-specific interpretation' taxonomic_confidence, m.url material_url,
       coalesce(e.evidence_url,t.source_url||'/general-information') identity_reference
from read_csv('data/identity.csv') i
join material m on i.material_id=m.id and m.origin in ('natural','both')
join note_frequency f on f.note_key=norm(i.note) and f.match_count=1
join note_material_match nm on nm.material_id=m.id and nm.note_key=f.note_key
join taxon t using(scientific_name)
left join read_csv('data/evidence.csv') e using(scientific_name);
create table botanical_shortlist as
select t.scientific_name,t.geographic_area, mt.*, f.perfumes,f.brands,
       dense_rank() over(order by f.perfumes desc,f.brands desc) frequency_rank
from material_taxon mt join taxon t using(plant_name_id) join note_frequency f using(note_key);
create table taxon_distribution as select * from read_csv('data/raw/ranges.csv',all_varchar=true);
create table taxon_native_region as select * from taxon_distribution
where introduced='0' and extinct='0' and location_doubtful='0';
create table ecoregion_observation as
select s.WCVP_ID plant_name_id,s.species,s.WFO_ID,e.ECO_ID,e.ECO_NAME,e.BIOME_NAME,e.REALM,
       p.n observations,p."overlap.1000km2" overlap_thousand_km2,p."ecoregion.perc" ecoregion_percent,
       p."native.perc" native_percent,'https://doi.org/10.5281/zenodo.13166796' source_url
from read_csv('data/raw/tree_pairs.csv') p join read_csv('data/raw/tree_species.csv',all_varchar=true) s using(species)
join read_csv('data/raw/ecoregions.csv') e using(ECO_ID);
create table ecoregion_tree as select * from ecoregion_observation where ecoregion_percent>0;
create table gbif_evidence as
select usage.canonicalName scientific_name,usage.key gbif_key,usage.status status,
       diagnostics.matchType match_method,diagnostics.confidence confidence,
       'https://www.gbif.org/species/'||usage.key source_url
from read_json_auto('data/raw/gbif_*.json') where diagnostics.matchType='EXACT' and usage.rank='SPECIES';
create table candidate_taxa as
select b.*, reason, g.gbif_key,
       (select count(distinct area_code_l3) from taxon_native_region n where n.plant_name_id=b.plant_name_id) native_areas,
       (select count(distinct ECO_ID) from ecoregion_tree e where e.plant_name_id=b.plant_name_id) expected_native_ecoregions
from botanical_shortlist b join read_csv('data/selection.csv') using(scientific_name)
left join gbif_evidence g using(scientific_name) order by perfumes desc;
-- Evidence coverage at the joint grain; EXISTS avoids multiplication by country or note position.
create table candidate_coverage as
select c.scientific_name,count(distinct n.perfume_id) perfumes,count(distinct n.brand) brands,
count(distinct n.perfume_id) filter(where b.brand is not null) perfumes_with_house_country,
count(distinct n.brand) filter(where b.brand is not null) brands_with_house_country
from candidate_taxa c join perfume_note n using(note_key)
left join (select distinct brand from brand_origin where reference='Scento' and reported_country is not null) b using(brand)
group by c.scientific_name;
create table analysis_cohort as
select distinct n.perfume_id,n.brand,c.plant_name_id,c.scientific_name,b.country_count,
b.reported_countries,b.verified_founding_country
from candidate_taxa c join perfume_note n using(note_key) left join brand_country_review b using(brand);

create table dictionary_coverage as
select dictionary_match,count(*) note_keys,sum(top_mentions + middle_mentions + base_mentions) mentions
from note_frequency group by dictionary_match;

create table raw_note_frequency as
select note, note_key,count(distinct perfume_id) perfumes,count(distinct brand) brands,
       count(distinct perfume_id) filter(position='top') top_perfumes,
       count(distinct perfume_id) filter(position='middle') middle_perfumes,
       count(distinct perfume_id) filter(position='base') base_perfumes,
       any_value(dictionary_match) dictionary_match
from (select perfume_id,brand,position,trim(token) note,norm(token) note_key
      from perfume_source, lateral (values ('top',Top_Notes),('middle',Middle_Notes),('base',Base_Notes)) s(position,notes),
      unnest(string_split(notes,',')) t(token) where trim(token)!='') r
join note_frequency using(note_key) group by note,note_key;
