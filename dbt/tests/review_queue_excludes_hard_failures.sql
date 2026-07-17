select queue.thinker_qid, queue.quote_id
from {{ ref('quote_review_queue') }} as queue
join {{ ref('fct_quotes') }} as quotes
    on queue.thinker_qid = quotes.thinker_qid
    and queue.quote_id = quotes.quote_id
where {{ var('validate_editorial_queue', true) }}
  and (
      quotes.citation_only
      or quotes.attributed
      or quotes.leading_fragment
      or quotes.attribution_section
      or quotes.very_long
  )
