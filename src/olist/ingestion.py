"""Load unchanged Olist CSV files into DuckDB tables."""

from dataclasses import dataclass
from pathlib import Path

from olist.paths import RAW_DATA_DIR, WAREHOUSE_PATH
from olist.warehouse import connect

SOURCE_TABLES = {
    "ecommerce/olist_customers_dataset.csv": "customers",
    "ecommerce/olist_geolocation_dataset.csv": "geolocation",
    "ecommerce/olist_order_items_dataset.csv": "order_items",
    "ecommerce/olist_order_payments_dataset.csv": "order_payments",
    "ecommerce/olist_order_reviews_dataset.csv": "order_reviews",
    "ecommerce/olist_orders_dataset.csv": "orders",
    "ecommerce/olist_products_dataset.csv": "products",
    "ecommerce/olist_sellers_dataset.csv": "sellers",
    "ecommerce/product_category_name_translation.csv": "product_category_name_translation",
    "seller-funnel/olist_closed_deals_dataset.csv": "closed_deals",
    "seller-funnel/olist_marketing_qualified_leads_dataset.csv": "marketing_qualified_leads",
}


@dataclass(frozen=True)
class LoadResult:
    table: str
    rows: int


def _sql_literal(value: str) -> str:
    """Return a single-quoted SQL literal with embedded quotes escaped.

    Examples:
    >>> _sql_literal("Smith")
    "'Smith'"

    >>> _sql_literal("O'Connor")
    "'O''Connor'"
    """

    return "'" + value.replace("'", "''") + "'"


def _source_paths(raw_data_dir: Path) -> dict[Path, str]:
    sources = {
        raw_data_dir / relative_path: table for relative_path, table in SOURCE_TABLES.items()
    }
    missing = [path for path in sources if not path.is_file()]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Missing source files:\n{formatted}")
    return sources


def load_raw_data(
    raw_data_dir: Path = RAW_DATA_DIR,
    warehouse_path: Path = WAREHOUSE_PATH,
) -> list[LoadResult]:
    """Replace all raw tables from their source CSVs in one transaction."""

    sources = _source_paths(raw_data_dir)
    connection = connect(warehouse_path)
    results: list[LoadResult] = []

    try:
        connection.execute("BEGIN TRANSACTION")
        connection.execute("CREATE SCHEMA IF NOT EXISTS raw")

        for source_path, table in sources.items():
            source = _sql_literal(str(source_path))
            source_name = _sql_literal(source_path.relative_to(raw_data_dir).as_posix())
            connection.execute(
                f"""--sql
                CREATE OR REPLACE TABLE raw.{table} AS
                SELECT
                    *,
                    {source_name}::VARCHAR AS _source_file,
                    current_timestamp AS _loaded_at
                FROM read_csv(
                    {source},
                    header = true,
                    all_varchar = true,
                    sample_size = -1
                )
                """
            )
            rows = connection.execute(f"SELECT count(*) FROM raw.{table}").fetchone()
            assert rows is not None
            results.append(LoadResult(table=table, rows=rows[0]))

        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()

    return results
