{{ config(materialized="table") }}

-- Load the eligible order-level delivery observations used throughout the model.
with delivery_performance as (
    select * from {{ ref("fct_delivery_performance") }}
),

-- Latest purchase date among delivered orders only, so this lags the true latest purchase
-- (undelivered/canceled orders can be more recent) and can still miss slow deliveries.
latest_purchase as (
    select max(cast(purchased_at as date)) as latest_purchase_date
    from delivery_performance
),

-- Last calendar month complete in the latest year (partial August -> July).
-- A partial January yields 0, so comparable_orders returns no rows for either year.
comparison_window as (
    select
        year(latest_purchase_date) as latest_year,
        case
            when latest_purchase_date = last_day(latest_purchase_date)
            then month(latest_purchase_date)
            else month(latest_purchase_date) - 1
        end as last_complete_month
    from latest_purchase
),

-- Select the latest two years over the same January-to-last-complete-month period.
comparable_orders as (
    select
        year(delivery_performance.purchased_at) as purchase_year,
        month(delivery_performance.purchased_at) as purchase_month_number,
        strftime(delivery_performance.purchased_at, '%b') as purchase_month_name,
        case
            when year(delivery_performance.purchased_at) = comparison_window.latest_year
                then 'Current year'
            else 'Previous year'
        end as comparison_period,
        delivery_performance.delivery_difference_days
    from delivery_performance
    cross join comparison_window
    where
        year(delivery_performance.purchased_at)
        between comparison_window.latest_year - 1 and comparison_window.latest_year
        and month(delivery_performance.purchased_at) <= comparison_window.last_complete_month
),

-- Calculate the monthly count, mean, and selected percentiles for each comparison year.
distribution_statistics as (
    select
        purchase_year,
        purchase_month_number,
        purchase_month_name,
        comparison_period,
        count(*) as eligible_delivered_orders,
        avg(delivery_difference_days) as average_delivery_difference_days,
        quantile_cont(delivery_difference_days, 0.01) as p01_delivery_difference_days,
        quantile_cont(delivery_difference_days, 0.05) as p05_delivery_difference_days,
        quantile_cont(delivery_difference_days, 0.125) as p12_5_delivery_difference_days,
        quantile_cont(delivery_difference_days, 0.25) as first_quartile_delivery_difference_days,
        median(delivery_difference_days) as median_delivery_difference_days,
        quantile_cont(delivery_difference_days, 0.75) as third_quartile_delivery_difference_days,
        quantile_cont(delivery_difference_days, 0.875) as p87_5_delivery_difference_days,
        quantile_cont(delivery_difference_days, 0.95) as p95_delivery_difference_days,
        quantile_cont(delivery_difference_days, 0.99) as p99_delivery_difference_days
    from comparable_orders
    group by
        purchase_year,
        purchase_month_number,
        purchase_month_name,
        comparison_period
),

-- Derive Tukey whiskers from the order-level observations.
boxplot_statistics as (
    select
        distribution_statistics.*,
        min(comparable_orders.delivery_difference_days) filter (
            where
                comparable_orders.delivery_difference_days
                >= distribution_statistics.first_quartile_delivery_difference_days
                - 1.5 * (
                    distribution_statistics.third_quartile_delivery_difference_days
                    - distribution_statistics.first_quartile_delivery_difference_days
                )
        ) as lower_whisker_delivery_difference_days,
        max(comparable_orders.delivery_difference_days) filter (
            where
                comparable_orders.delivery_difference_days
                <= distribution_statistics.third_quartile_delivery_difference_days
                + 1.5 * (
                    distribution_statistics.third_quartile_delivery_difference_days
                    - distribution_statistics.first_quartile_delivery_difference_days
                )
        ) as upper_whisker_delivery_difference_days,
    from distribution_statistics
    inner join comparable_orders using (
        purchase_year,
        purchase_month_number,
        purchase_month_name,
        comparison_period
    )
    group by all
)

-- p01/p99 feed fct_delivery_difference_outliers' thresholds.
select
    purchase_year,
    purchase_month_number,
    purchase_month_name,
    comparison_period,
    eligible_delivered_orders,
    average_delivery_difference_days,
    p01_delivery_difference_days,
    p05_delivery_difference_days,
    p12_5_delivery_difference_days,
    lower_whisker_delivery_difference_days,
    first_quartile_delivery_difference_days,
    median_delivery_difference_days,
    third_quartile_delivery_difference_days,
    upper_whisker_delivery_difference_days,
    p87_5_delivery_difference_days,
    p95_delivery_difference_days,
    p99_delivery_difference_days
from boxplot_statistics
order by purchase_month_number, purchase_year
