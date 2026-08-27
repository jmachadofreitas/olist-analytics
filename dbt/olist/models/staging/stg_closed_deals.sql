select
    mql_id,
    seller_id,
    sdr_id,
    sr_id,
    cast(won_date as timestamp) as won_at,
    business_segment,
    lead_type,
    lead_behaviour_profile,
    cast(has_company as boolean) as has_company,
    cast(has_gtin as boolean) as has_gtin,
    average_stock,
    business_type,
    cast(declared_product_catalog_size as integer) as declared_product_catalog_size,
    cast(declared_monthly_revenue as decimal(18, 2)) as declared_monthly_revenue,
    _source_file,
    _loaded_at
from {{ source("olist_raw", "closed_deals") }}
