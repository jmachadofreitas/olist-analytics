select
    geolocation_zip_code_prefix,
    cast(geolocation_lat as double) as geolocation_lat,
    cast(geolocation_lng as double) as geolocation_lng,
    geolocation_city,
    geolocation_state,
    _source_file,
    _loaded_at
from {{ source("olist_raw", "geolocation") }}
