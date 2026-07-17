with counts as (
    select
        thinkers.thinker_qid,
        count(queue.quote_id) as candidate_count
    from {{ ref('dim_thinkers') }} as thinkers
    left join {{ ref('quote_review_queue') }} as queue
        on thinkers.thinker_qid = queue.thinker_qid
    group by thinkers.thinker_qid
)
select thinker_qid, candidate_count
from counts
where {{ var('validate_editorial_queue', true) }}
  and (
      (thinker_qid = 'Q7186' and candidate_count != 0)
      or (thinker_qid != 'Q7186' and candidate_count != 2)
  )
