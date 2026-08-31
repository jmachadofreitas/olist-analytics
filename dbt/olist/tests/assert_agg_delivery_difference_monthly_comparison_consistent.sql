select *
from {{ ref("agg_delivery_difference_monthly_comparison") }}
where not (
    lower_whisker_delivery_difference_days
    <= first_quartile_delivery_difference_days
    and first_quartile_delivery_difference_days <= median_delivery_difference_days
    and median_delivery_difference_days <= third_quartile_delivery_difference_days
    and third_quartile_delivery_difference_days <= upper_whisker_delivery_difference_days
)
or not (
    p01_delivery_difference_days <= p05_delivery_difference_days
    and p05_delivery_difference_days <= p12_5_delivery_difference_days
    and p12_5_delivery_difference_days <= first_quartile_delivery_difference_days
    and first_quartile_delivery_difference_days <= median_delivery_difference_days
    and median_delivery_difference_days <= third_quartile_delivery_difference_days
    and third_quartile_delivery_difference_days <= p87_5_delivery_difference_days
    and p87_5_delivery_difference_days <= p95_delivery_difference_days
    and p95_delivery_difference_days <= p99_delivery_difference_days
)
