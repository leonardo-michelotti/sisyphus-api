select quote_id
from {{ ref('stg_quotes') }}
where regexp_matches(quote_text, '\[[0-9]+\]$')
   or regexp_matches(quote_text, '"$')
   or regexp_matches(quote_text, '"[.!?]$')
