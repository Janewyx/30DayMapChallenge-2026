create macro norm(s) as trim(regexp_replace(lower(strip_accents(nfc_normalize(s))), '[^\p{L}\p{N}]+', ' ', 'g'));
create table perfume_source as
select row_number() over () source_row, md5(URL) perfume_id, Number source_number, Name perfume_name, Brand brand,
       norm(Brand) brand_key, try_cast(Release_Year as integer) release_year, Perfumers perfumers,
       URL source_url, Top_Notes, Middle_Notes, Base_Notes
from read_csv('data/raw/parfumo.csv', all_varchar=true, nullstr='NA', parallel=false);
-- A URL can recur in the source. Keep its most complete description and all raw rows.
create table perfume as select * from perfume_source
qualify row_number() over (partition by perfume_id order by
  ((release_year is not null)::int + (perfumers is not null)::int) desc, source_row)=1;
create table perfume_note as
select perfume_id, source_row, p.brand, p.perfumers, p.release_year, position, note_order, trim(token) note, norm(token) note_key
from perfume_source p, lateral (values ('top',Top_Notes),('middle',Middle_Notes),('base',Base_Notes)) s(position,notes),
unnest(string_split(notes, ',')) with ordinality as t(token,note_order)
where trim(token) != ''
qualify row_number() over(partition by perfume_id,position,norm(token) order by source_row,note_order)=1;
create table material as select * from read_csv('data/raw/materials.csv', all_varchar=true);
create table material_label as
select id material_id, name source_label, norm(name) note_key, 'exact' match_method from material
union all
select id, trim(a), norm(a), 'alias' from material, unnest(string_split(aliases,';')) t(a) where trim(a)!='';
create table note_material_match as
select distinct n.note_key, m.material_id, m.source_label, m.match_method
from (select distinct note_key from perfume_note) n join material_label m using(note_key);
create table note_frequency as
with stats as (
select note_key, min(note) example_label, count(distinct perfume_id) perfumes, count(distinct brand) brands,
count(*) filter(position='top') top_mentions,count(*) filter(position='middle') middle_mentions,
count(*) filter(position='base') base_mentions
from perfume_note group by note_key)
select stats.*, count(distinct material_id) match_count,
case when bool_or(match_method='exact') then 'exact' when count(material_id)>0 then 'alias' else 'unmatched' end dictionary_match
from stats left join note_material_match using(note_key) group by all;
create table house as select * from read_csv('data/raw/houses.csv', all_varchar=true);
create table brand_origin as
with brands as (select distinct brand,brand_key from perfume)
select brand, brand_key, 'Scento' as reference, h.id source_id, h.name source_name, h.country reported_country,
       'house country' country_meaning, h.url source_url, 'normalized exact' match_method
from brands join house h on brand_key=norm(h.name)
union all
select brand,brand_key,'Parfica / Wikidata',wikidata_qid,b.name,b.country,'P17 or P495',
       'https://www.wikidata.org/wiki/'||wikidata_qid,'normalized exact'
from brands join read_csv('data/raw/brands.csv', all_varchar=true) b on brand_key=norm(b.name);
create table brand_founding as
select distinct p.brand,f.founding_country,f.founding_place,f.founding_year,f.source_url
from perfume p join read_csv('data/founding.csv') f on p.brand_key=norm(f.brand);
create table brand_country_review as
select p.brand,count(distinct o.reported_country) country_count,
       string_agg(distinct o.reported_country,' | ' order by o.reported_country) reported_countries,
       max(f.founding_country) verified_founding_country
from (select distinct brand from perfume where brand is not null) p
left join brand_origin o using(brand) left join brand_founding f using(brand) group by p.brand;
