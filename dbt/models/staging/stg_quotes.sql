with source as (
    select * from {{ source('bronze', 'bronze_quotes') }}
),
normalized as (
    select
        lower(hex(md5(thinker_qid || '|' || regexp_replace(trim(text), '\\s+', ' ', 'g')))) as quote_id,
        thinker_qid,
        thinker_name,
        regexp_replace(trim(text), '\\s+', ' ', 'g') as quote_text,
        category,
        work,
        source_url,
        source_revision,
        fetched_at,
        length(regexp_replace(trim(text), '\\s+', ' ', 'g')) as character_count
    from source
)
select * from normalized
qualify row_number() over (partition by quote_id order by fetched_at desc) = 1
