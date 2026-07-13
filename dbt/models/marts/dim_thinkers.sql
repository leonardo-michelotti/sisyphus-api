select
    qid as thinker_qid,
    name as thinker_name,
    wikiquote_title,
    source_url,
    source_revision,
    fetched_at
from {{ source('bronze', 'bronze_thinkers') }}
qualify row_number() over (partition by qid order by fetched_at desc) = 1
