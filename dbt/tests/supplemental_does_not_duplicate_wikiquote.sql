select supplemental.quote_id
from {{ ref('stg_quotes') }} as supplemental
join {{ ref('stg_quotes') }} as wikiquote
  on supplemental.quote_id = wikiquote.quote_id
where supplemental.source_kind = 'supplemental'
  and wikiquote.source_kind = 'wikiquote'
