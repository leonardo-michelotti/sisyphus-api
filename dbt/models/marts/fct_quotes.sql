with assessed as (
    select
        *,
        regexp_matches(quote_text, '^[[:alnum:] ._-]+[IVXLCDM]+[.]?[ ]*[0-9. -]*$') as citation_only,
        category = 'atribuida' as attributed,
        regexp_matches(quote_text, '^(\.\.\.|\(\.\.\.\))') as leading_fragment,
        lower(coalesce(work, '')) like '%atribu%' as attribution_section,
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
            case when attributed then 'attributed_quote' end,
            case when leading_fragment then 'leading_fragment' end,
            case when attribution_section then 'attribution_section' end
        ], reason -> reason is not null) as quality_reasons
    from assessed
),
curated as (
    select
        classified.*,
        selection.quote_id is not null as editorial_approved
    from classified
    left join {{ ref('daily_quote_selection') }} selection
        on classified.quote_id = selection.quote_id
        and classified.thinker_qid = selection.thinker_qid
)
select
    *,
    case
        when citation_only then 'rejected'
        when very_short or very_long or attributed or leading_fragment or attribution_section
            then 'review'
        else 'accepted'
    end as curation_status,
    case
        when len(quality_reasons) = 0 then 'passed_automatic_rules'
        else quality_reasons[1]
    end as quality_reason,
    not citation_only
        and not very_short
        and not very_long
        and not attributed
        and not leading_fragment
        and not attribution_section as passes_automatic_rules,
    not citation_only
        and not very_short
        and not very_long
        and not attributed
        and not leading_fragment
        and not attribution_section
        and editorial_approved as is_daily_eligible
from curated
