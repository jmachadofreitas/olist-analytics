select
    order_id,
    cast(order_item_id as integer) as order_item_id,
    product_id,
    seller_id,
    cast(shipping_limit_date as timestamp) as shipping_limit_at,
    cast(price as decimal(18, 2)) as price,
    cast(freight_value as decimal(18, 2)) as freight_value,
    _source_file,
    _loaded_at
from {{ source("olist_raw", "order_items") }}
