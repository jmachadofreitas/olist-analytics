select
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    o.order_status,
    o.purchased_at,
    o.approved_at,
    o.delivered_to_carrier_at,
    o.delivered_to_customer_at,
    o.estimated_delivery_at
from {{ ref("stg_orders") }} as o
left join {{ ref("stg_customers") }} as c
    on o.customer_id = c.customer_id