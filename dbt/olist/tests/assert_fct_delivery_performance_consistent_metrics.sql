select *
from {{ ref("fct_delivery_performance") }}
where
    delivery_difference_days != date_diff(
        'day',
        estimated_delivery_date,
        delivered_to_customer_date
    )
    or is_on_time != (delivery_difference_days <= 0)
