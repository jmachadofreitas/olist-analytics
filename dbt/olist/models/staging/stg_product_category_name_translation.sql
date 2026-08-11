select
    product_category_name,
    product_category_name_english,
    _source_file,
    _loaded_at
from {{ source("olist_raw", "product_category_name_translation") }}
