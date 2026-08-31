{{ config(materialized="table") }}

-- Summarize delivery volume and performance for cohorts grouped by purchase month.
select
    cast(date_trunc('month', purchased_at) as date) as purchase_month,
    count(*) as eligible_delivered_orders,
    count(*) filter (where is_on_time) as on_time_orders,
    round(
        100.0 * count(*) filter (where is_on_time) / count(*),
        2
    ) as on_time_delivery_rate_pct,
    round(avg(delivery_difference_days), 2) as average_delivery_difference_days
from {{ ref("fct_delivery_performance") }}
group by purchase_month
