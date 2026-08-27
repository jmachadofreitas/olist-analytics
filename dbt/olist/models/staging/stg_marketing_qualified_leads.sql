select
    mql_id,
    cast(first_contact_date as date) as first_contact_date,
    landing_page_id,
    origin,
    _source_file,
    _loaded_at
from {{ source("olist_raw", "marketing_qualified_leads") }}
