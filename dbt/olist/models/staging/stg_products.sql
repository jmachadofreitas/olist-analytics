select
    product_id,
    product_category_name,
    cast(product_name_lenght as integer) as product_name_length,
    cast(product_description_lenght as integer) as product_description_length,
    cast(product_photos_qty as integer) as product_photo_count,
    cast(product_weight_g as double) as product_weight_g,
    cast(product_length_cm as double) as product_length_cm,
    cast(product_height_cm as double) as product_height_cm,
    cast(product_width_cm as double) as product_width_cm,
    _source_file,
    _loaded_at
from {{ source("olist_raw", "products") }}
