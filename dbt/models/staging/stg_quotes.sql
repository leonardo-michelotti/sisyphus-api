with source as (
    select * from {{ source('bronze', 'bronze_quotes') }}
),
normalized as (
    select
        thinker_qid,
        thinker_name,
        regexp_replace(trim(text), '\\s+', ' ', 'g') as quote_text,
        category,
        work,
        source_url,
        source_name,
        source_license,
        source_revision,
        fetched_at,
        length(regexp_replace(trim(text), '\\s+', ' ', 'g')) as character_count
    from source
),
identified as (
    select
        sha256(thinker_qid || '|' || quote_text) as quote_id,
        *
    from normalized
),
with_occurrence as (
    select
        sha256(
            quote_id || '|' || category || '|' || coalesce(work, '') || '|' || source_revision
        ) as occurrence_id,
        *
    from identified
)
select * from with_occurrence
qualify row_number() over (partition by occurrence_id order by fetched_at desc) = 1
