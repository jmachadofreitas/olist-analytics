"""Load unchanged Olist CSV files into DuckDB tables."""

from pathlib import Path

from common.io.ingestion import LoadResult, load_csv_tables
from olist.ingestion.catalog import SOURCE_TABLES
from olist.paths import WAREHOUSE_PATH, project_root

RAW_DATA_DIR = project_root() / "data" / "raw"

__all__ = ["LoadResult", "SOURCE_TABLES", "load_raw_data"]


def load_raw_data(
    raw_data_dir: Path = RAW_DATA_DIR,
    warehouse_path: Path = WAREHOUSE_PATH,
) -> list[LoadResult]:
    return load_csv_tables(raw_data_dir, warehouse_path, SOURCE_TABLES)
