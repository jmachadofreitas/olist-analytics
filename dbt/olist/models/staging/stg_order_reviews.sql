select
    review_id,
    order_id,
    cast(review_score as integer) as review_score,
    review_comment_title,
    review_comment_message,
    cast(review_creation_date as date) as review_request_date,
    cast(review_answer_timestamp as timestamp) as review_answered_at,
    _source_file,
    _loaded_at
from {{ source("olist_raw", "order_reviews") }}
