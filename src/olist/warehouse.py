"""DuckDB connection helpers."""

from pathlib import Path

import duckdb


def connect(warehouse_path: Path) -> duckdb.DuckDBPyConnection:
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(warehouse_path))


def quote_identifier(value: str) -> str:
    """Quote a table or column name before placing it in generated SQL."""
    return '"' + value.replace('"', '""') + '"'
