"""Load CSV files into DuckDB raw tables."""

from dataclasses import dataclass
from pathlib import Path

import duckdb
from duckdb import DuckDBPyConnection


@dataclass
class LoadResult:
    table: str
    rows: int

def connect(warehouse_path: Path, *, read_only: bool = False) -> DuckDBPyConnection:
    """Create a DuckDB connection to the warehouse file."""
    if not read_only:
        warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(warehouse_path), read_only=read_only)


def quote_identifier(value: str) -> str:
    """Quote a table or column name before placing it in generated SQL."""
    return '"' + value.replace('"', '""') + '"'


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def load_csv_tables(
    raw_data_dir: Path,
    warehouse_path: Path,
    source_tables: dict[str, str],
) -> list[LoadResult]:
    """Replace raw tables from CSVs in one transaction."""

    sources = {
        raw_data_dir / relative_path: table for relative_path, table in source_tables.items()
    }
    missing = [path for path in sources if not path.is_file()]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Missing source files:\n{formatted}")

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
