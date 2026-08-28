-- Delivery KPIs require a completed delivery and both sides of the date comparison.
with eligible_orders as (
    select
        order_id,
        customer_id,
        order_status,
        purchased_at,
        delivered_to_customer_at,
        estimated_delivery_at,
        cast(delivered_to_customer_at as date) as delivered_to_customer_date,
        cast(estimated_delivery_at as date) as estimated_delivery_date
    from {{ ref("fct_orders") }}
    where
        order_status = 'delivered'
        and delivered_to_customer_at is not null
        and estimated_delivery_at is not null
)

-- delivery_difference_days: Negative values are early, zero is on time, and positive values are late.
select
    order_id,
    customer_id,
    order_status,
    purchased_at,
    delivered_to_customer_at,
    estimated_delivery_at,
    delivered_to_customer_date,
    estimated_delivery_date,
    date_diff(
        'day',
        estimated_delivery_date,
        delivered_to_customer_date
    ) as delivery_difference_days,
    delivered_to_customer_date <= estimated_delivery_date as is_on_time
from eligible_orders
