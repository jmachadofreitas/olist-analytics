select
    review_id,
    order_id
from {{ ref("stg_order_reviews") }}
group by review_id, order_id
having count(*) > 1
