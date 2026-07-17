select *
from {{ ref('stg_quotes') }}
where source_kind = 'supplemental'
  and (
    (
      original_text is not null
      and (
        original_language is null
        or translator_name is null
        or translation_license is null
        or translation_url is null
      )
    )
    or (
      original_text is null
      and (
        original_language is not null
        or translator_name is not null
        or translation_license is not null
        or translation_url is not null
      )
    )
  )
