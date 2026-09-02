select *
from {{ ref("agg_delivery_performance_monthly") }}
where
    eligible_delivered_orders <= 0
    or on_time_orders < 0
    or on_time_orders > eligible_delivered_orders
    or on_time_delivery_rate_pct != round(
        100.0 * on_time_orders / eligible_delivered_orders,
        2
    )
