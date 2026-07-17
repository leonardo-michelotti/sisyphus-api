with matched as (
    select
        queue.thinker_qid,
        quotes.thinker_name,
        queue.quote_id,
        queue.review_status,
        queue.review_reason,
        quotes.quote_text,
        quotes.category,
        quotes.work,
        quotes.character_count,
        quotes.curation_status,
        quotes.quality_reasons,
        quotes.source_name,
        quotes.source_license,
        quotes.source_url,
        quotes.source_revision,
        row_number() over (
            partition by queue.quote_id
            order by quotes.source_revision desc, quotes.occurrence_id
        ) as occurrence_rank
    from {{ ref('quote_review_queue') }} as queue
    join {{ ref('fct_quotes') }} as quotes
        on queue.thinker_qid = quotes.thinker_qid
        and queue.quote_id = quotes.quote_id
)
select * exclude (occurrence_rank)
from matched
where occurrence_rank = 1
order by thinker_name, quote_id
