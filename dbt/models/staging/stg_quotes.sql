with source as (
    select
        thinker_qid,
        thinker_name,
        text,
        null::varchar as original_text,
        null::varchar as original_language,
        category,
        work,
        source_url,
        source_name,
        source_license,
        source_revision,
        null::varchar as translator_name,
        null::varchar as translation_license,
        null::varchar as translation_url,
        fetched_at,
        'wikiquote'::varchar as source_kind
    from {{ source('bronze', 'bronze_quotes') }}

    union all

    select
        thinker_qid,
        thinker_name,
        text,
        original_text,
        original_language,
        category,
        work,
        source_url,
        source_name,
        source_license,
        source_revision,
        translator_name,
        translation_license,
        translation_url,
        reviewed_at as fetched_at,
        'supplemental'::varchar as source_kind
    from {{ source('bronze', 'bronze_supplemental_quotes') }}
),
whitespace_normalized as (
    select
        *,
        regexp_replace(trim(text), '\s+', ' ', 'g') as normalized_text
    from source
),
source_artifacts_removed as (
    select
        *,
        regexp_replace(
            regexp_replace(
                regexp_replace(normalized_text, '[ ]*(\[[0-9]+\])+$', ''),
                '"$', ''
            ),
            '"([.!?])$', '\1'
        ) as quote_text
    from whitespace_normalized
),
normalized as (
    select
        thinker_qid,
        thinker_name,
        quote_text,
        original_text,
        original_language,
        category,
        work,
        source_url,
        source_name,
        source_license,
        source_revision,
        translator_name,
        translation_license,
        translation_url,
        fetched_at,
        source_kind,
        length(quote_text) as character_count
    from source_artifacts_removed
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
            quote_id || '|' || category || '|' || coalesce(work, '') || '|'
            || source_revision || '|' || source_url
        ) as occurrence_id,
        *
    from identified
)
select * from with_occurrence
qualify row_number() over (partition by occurrence_id order by fetched_at desc) = 1
