select quote_id
from {{ ref('fct_quotes') }}
where attribution_section and is_daily_eligible
