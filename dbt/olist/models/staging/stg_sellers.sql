select
    seller_id,
    seller_zip_code_prefix,
    seller_city,
    seller_state,
    _source_file,
    _loaded_at
from {{ source("olist_raw", "sellers") }}
