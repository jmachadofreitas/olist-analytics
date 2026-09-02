with fact_totals as (
    select
        count(*) as eligible_delivered_orders,
        count(*) filter (where is_on_time) as on_time_orders
    from {{ ref("fct_delivery_performance") }}
),

aggregate_totals as (
    select
        sum(eligible_delivered_orders) as eligible_delivered_orders,
        sum(on_time_orders) as on_time_orders
    from {{ ref("agg_delivery_performance_monthly") }}
)

select
    fact_totals.eligible_delivered_orders as fact_eligible_delivered_orders,
    aggregate_totals.eligible_delivered_orders as aggregate_eligible_delivered_orders,
    fact_totals.on_time_orders as fact_on_time_orders,
    aggregate_totals.on_time_orders as aggregate_on_time_orders
from fact_totals
cross join aggregate_totals
where
    fact_totals.eligible_delivered_orders != aggregate_totals.eligible_delivered_orders
    or fact_totals.on_time_orders != aggregate_totals.on_time_orders
