select quote_id
from {{ ref('fct_quotes') }}
where citation_only and is_daily_eligible
