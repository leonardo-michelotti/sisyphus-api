select queue.thinker_qid, queue.quote_id
from {{ ref('quote_review_queue') }} as queue
left join {{ ref('fct_quotes') }} as quotes
    on queue.thinker_qid = quotes.thinker_qid
    and queue.quote_id = quotes.quote_id
where {{ var('validate_editorial_queue', true) }}
  and quotes.quote_id is null
