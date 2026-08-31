with monthly_coverage as (
    select
        purchase_month_number,
        count(*) as compared_years,
        max(purchase_year) - min(purchase_year) as year_gap
    from {{ ref("agg_delivery_difference_monthly_comparison") }}
    group by purchase_month_number
)

select *
from monthly_coverage
where compared_years != 2 or year_gap != 1
