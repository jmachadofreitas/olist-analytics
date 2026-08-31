{{ config(materialized="table") }}

with delivery_performance as (
    select * from {{ ref("fct_delivery_performance") }}
),


-- Pre-computed monthly boundaries
monthly_boundaries as (
    select
        purchase_year,
        purchase_month_number,
        purchase_month_name,
        comparison_period,
        lower_whisker_delivery_difference_days,
        upper_whisker_delivery_difference_days,
        p01_delivery_difference_days,
        p99_delivery_difference_days
    from {{ ref("agg_delivery_difference_monthly_comparison") }}
),

classified_orders as (
    select
        delivery_performance.order_id,
        delivery_performance.customer_id,
        delivery_performance.purchased_at,
        monthly_boundaries.purchase_year,
        monthly_boundaries.purchase_month_number,
        monthly_boundaries.purchase_month_name,
        monthly_boundaries.comparison_period,
        delivery_performance.delivery_difference_days,
        delivery_performance.delivery_difference_days
        < monthly_boundaries.lower_whisker_delivery_difference_days
            as is_lower_tukey_outlier,
        delivery_performance.delivery_difference_days
        > monthly_boundaries.upper_whisker_delivery_difference_days
            as is_upper_tukey_outlier,
        delivery_performance.delivery_difference_days < monthly_boundaries.p01_delivery_difference_days
            as is_lower_p01_p99_extreme,
        delivery_performance.delivery_difference_days > monthly_boundaries.p99_delivery_difference_days
            as is_upper_p01_p99_extreme
    from delivery_performance
    inner join monthly_boundaries
        on year(delivery_performance.purchased_at) = monthly_boundaries.purchase_year
        and month(delivery_performance.purchased_at) = monthly_boundaries.purchase_month_number
),

outliers as (
    select
        *,
        is_lower_tukey_outlier or is_upper_tukey_outlier as is_tukey_outlier,
        is_lower_p01_p99_extreme or is_upper_p01_p99_extreme as is_p01_p99_extreme
    from classified_orders
)

select
    order_id,
    customer_id,
    purchased_at,
    purchase_year,
    purchase_month_number,
    purchase_month_name,
    comparison_period,
    delivery_difference_days,
    is_tukey_outlier,
    is_lower_tukey_outlier,
    is_upper_tukey_outlier,
    is_p01_p99_extreme,
    is_lower_p01_p99_extreme,
    is_upper_p01_p99_extreme
from outliers
where is_tukey_outlier or is_p01_p99_extreme
order by
    purchase_month_number,
    purchase_year,
    delivery_difference_days,
    order_id
