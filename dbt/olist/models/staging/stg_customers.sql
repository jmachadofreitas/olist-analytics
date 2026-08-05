select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state,
    _source_file,
    _loaded_at
from {{ source("olist_raw", "customers") }}
