select
    order_id,
    payment_sequential
from {{ ref("stg_order_payments") }}
group by order_id, payment_sequential
having count(*) > 1
