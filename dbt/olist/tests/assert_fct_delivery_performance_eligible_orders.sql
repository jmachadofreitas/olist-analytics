with expected_orders as (
    select order_id
    from {{ ref("fct_orders") }}
    where
        order_status = 'delivered'
        and delivered_to_customer_at is not null
        and estimated_delivery_at is not null
),

actual_orders as (
    select order_id
    from {{ ref("fct_delivery_performance") }}
)

select
    coalesce(expected_orders.order_id, actual_orders.order_id) as order_id
from expected_orders
full outer join actual_orders using (order_id)
where expected_orders.order_id is null or actual_orders.order_id is null
