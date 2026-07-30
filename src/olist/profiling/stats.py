"""Collect descriptive statistics about raw source tables and columns."""

import duckdb

from olist.warehouse import quote_identifier

type ColumnsByTable = dict[str, list[tuple[str, str]]]

CANDIDATE_STAGING_TYPES = {
    ("closed_deals", "won_date"): "TIMESTAMP",
    ("closed_deals", "has_company"): "BOOLEAN",
    ("closed_deals", "has_gtin"): "BOOLEAN",
    ("closed_deals", "declared_product_catalog_size"): "INTEGER",
    ("closed_deals", "declared_monthly_revenue"): "DECIMAL(18,2)",
    ("geolocation", "geolocation_lat"): "DOUBLE",
    ("geolocation", "geolocation_lng"): "DOUBLE",
    ("marketing_qualified_leads", "first_contact_date"): "DATE",
    ("order_items", "order_item_id"): "INTEGER",
    ("order_items", "shipping_limit_date"): "TIMESTAMP",
    ("order_items", "price"): "DECIMAL(18,2)",
    ("order_items", "freight_value"): "DECIMAL(18,2)",
    ("order_payments", "payment_sequential"): "INTEGER",
    ("order_payments", "payment_installments"): "INTEGER",
    ("order_payments", "payment_value"): "DECIMAL(18,2)",
    ("order_reviews", "review_score"): "INTEGER",
    ("order_reviews", "review_creation_date"): "TIMESTAMP",
    ("order_reviews", "review_answer_timestamp"): "TIMESTAMP",
    ("orders", "order_purchase_timestamp"): "TIMESTAMP",
    ("orders", "order_approved_at"): "TIMESTAMP",
    ("orders", "order_delivered_carrier_date"): "TIMESTAMP",
    ("orders", "order_delivered_customer_date"): "TIMESTAMP",
    ("orders", "order_estimated_delivery_date"): "TIMESTAMP",
    ("products", "product_name_lenght"): "INTEGER",
    ("products", "product_description_lenght"): "INTEGER",
    ("products", "product_photos_qty"): "INTEGER",
    ("products", "product_weight_g"): "DOUBLE",
    ("products", "product_length_cm"): "DOUBLE",
    ("products", "product_height_cm"): "DOUBLE",
    ("products", "product_width_cm"): "DOUBLE",
}


def list_raw_columns(connection: duckdb.DuckDBPyConnection) -> ColumnsByTable:
    """Return source columns grouped by raw table in source order."""

    # DuckDB's information_schema.columns has one metadata row per table column.
    # It provides column names and types without reading the tables' data rows.
    rows = connection.execute(
        """--sql
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'raw'
          AND column_name NOT IN ('_source_file', '_loaded_at')
        ORDER BY table_name, ordinal_position
        """
    ).fetchall()

    columns: ColumnsByTable = {}
    for table_name, column_name, data_type in rows:
        columns.setdefault(table_name, []).append((column_name, data_type))
    return columns

