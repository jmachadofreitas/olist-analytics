with outliers as (
    select * from {{ ref("fct_delivery_difference_outliers") }}
),

boundaries as (
    select
        purchase_year,
        purchase_month_number,
        comparison_period,
        lower_whisker_delivery_difference_days,
        upper_whisker_delivery_difference_days,
        p01_delivery_difference_days,
        p99_delivery_difference_days
    from {{ ref("agg_delivery_difference_monthly_comparison") }}
),

classified as (
    select
        outliers.*,
        outliers.delivery_difference_days < boundaries.lower_whisker_delivery_difference_days
            as expected_is_lower_tukey_outlier,
        outliers.delivery_difference_days > boundaries.upper_whisker_delivery_difference_days
            as expected_is_upper_tukey_outlier,
        outliers.delivery_difference_days < boundaries.p01_delivery_difference_days
            as expected_is_lower_p01_p99_extreme,
        outliers.delivery_difference_days > boundaries.p99_delivery_difference_days
            as expected_is_upper_p01_p99_extreme
    from outliers
    inner join boundaries using (
        purchase_year,
        purchase_month_number,
        comparison_period
    )
)

select *
from classified
where
    is_lower_tukey_outlier <> expected_is_lower_tukey_outlier
    or is_upper_tukey_outlier <> expected_is_upper_tukey_outlier
    or is_p01_p99_extreme
    <> (expected_is_lower_p01_p99_extreme or expected_is_upper_p01_p99_extreme)
    or is_lower_p01_p99_extreme <> expected_is_lower_p01_p99_extreme
    or is_upper_p01_p99_extreme <> expected_is_upper_p01_p99_extreme
    or is_tukey_outlier
    <> (expected_is_lower_tukey_outlier or expected_is_upper_tukey_outlier)
    or not (is_tukey_outlier or is_p01_p99_extreme)
