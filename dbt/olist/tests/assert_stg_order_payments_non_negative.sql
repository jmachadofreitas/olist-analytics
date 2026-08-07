select *
from {{ ref("stg_order_payments") }}
where payment_installments < 0 or payment_value < 0
