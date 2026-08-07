select
    order_id,
    cast(payment_sequential as integer) as payment_sequential,
    payment_type,
    cast(payment_installments as integer) as payment_installments,
    cast(payment_value as decimal(18, 2)) as payment_value,
    _source_file,
    _loaded_at
from {{ source("olist_raw", "order_payments") }}
