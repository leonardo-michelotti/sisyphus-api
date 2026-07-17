select
    thinkers.thinker_qid,
    count(quotes.quote_id) as daily_quote_count
from {{ ref('dim_thinkers') }} as thinkers
left join {{ ref('fct_quotes') }} as quotes
    on thinkers.thinker_qid = quotes.thinker_qid
    and quotes.is_daily_eligible
group by thinkers.thinker_qid
having count(quotes.quote_id) != {{ var('daily_quotes_per_thinker', 3) }}
