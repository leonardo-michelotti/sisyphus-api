with assessed as (
    select
        *,
        regexp_matches(quote_text, '^[[:alnum:] ._-]+[IVXLCDM]+[.]?[ ]*[0-9. -]*$') as citation_only,
        category = 'atribuida' as attributed,
        character_count < 40 as very_short,
        character_count > 500 as very_long
    from {{ ref('stg_quotes') }}
),
classified as (
    select
        *,
        list_filter([
            case when citation_only then 'citation_only' end,
            case when very_short then 'short_text' end,
            case when very_long then 'long_text' end,
            case when attributed then 'attributed_quote' end
        ], reason -> reason is not null) as quality_reasons
    from assessed
)
select
    *,
    case
        when citation_only then 'rejected'
        when very_short or very_long or attributed then 'review'
        else 'accepted'
    end as curation_status,
    case
        when len(quality_reasons) = 0 then 'passed_automatic_rules'
        else quality_reasons[1]
    end as quality_reason,
    not citation_only
        and not very_short
        and not very_long
        and not attributed as is_daily_eligible
from classified
