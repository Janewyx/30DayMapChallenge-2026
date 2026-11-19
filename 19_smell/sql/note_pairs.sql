copy (
    select a.scientific_name first_species, b.scientific_name second_species,
           count(distinct a.perfume_id) shared_perfumes
    from analysis_cohort a join analysis_cohort b
      on a.perfume_id=b.perfume_id and a.scientific_name<b.scientific_name
    group by a.scientific_name,b.scientific_name
    order by a.scientific_name,b.scientific_name
) to 'outputs/note_pairs.csv' (header);
