"""Collect descriptive statistics about raw source tables and columns."""

import duckdb

from common.io.ingestion import quote_identifier

type ColumnsByTable = dict[str, list[tuple[str, str]]]
type StagingTypes = dict[tuple[str, str], str]

MAX_DISTINCT_VALUES_FOR_FREQUENCY_PROFILE = 50
FREQUENCY_PROFILE_LIMIT = 10


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


def _record_table_statistics(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    table_name: str,
    column_count: int,
) -> int:
    """Persist row and column counts for one raw table."""

    table = f"raw.{quote_identifier(table_name)}"
    result = connection.execute(f"SELECT count(*) FROM {table}").fetchone()
    assert result is not None
    row_count = int(result[0])
    connection.execute(
        """--sql
        INSERT INTO audit.table_profiles (run_id, table_name, row_count, column_count)
        VALUES (?, ?, ?, ?)
        """,
        [run_id, table_name, row_count, column_count],
    )
    return row_count


def _record_column_statistics(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    table_name: str,
    column_name: str,
    data_type: str,
) -> int | None:
    """Persist missingness, cardinality, range, and length statistics for one column."""

    table = f"raw.{quote_identifier(table_name)}"
    column = quote_identifier(column_name)
    statistics = connection.execute(
        f"""--sql
        SELECT
            count(*) AS row_count,
            count(*) FILTER (WHERE {column} IS NULL) AS null_count,
            count(*) FILTER (WHERE trim({column}) = '') AS empty_count,
            approx_count_distinct({column}) AS approximate_distinct_count,
            min({column}) AS minimum_value,
            max({column}) AS maximum_value,
            min(length({column})) AS minimum_length,
            max(length({column})) AS maximum_length
        FROM {table}
        """
    ).fetchone()
    assert statistics is not None

    connection.execute(
        """--sql
        INSERT INTO audit.column_profiles (
            run_id,
            table_name,
            column_name,
            data_type,
            row_count,
            null_count,
            empty_count,
            approximate_distinct_count,
            minimum_value,
            maximum_value,
            minimum_length,
            maximum_length
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [run_id, table_name, column_name, data_type, *statistics],
    )
    approximate_distinct_count = statistics[3]
    return int(approximate_distinct_count) if approximate_distinct_count is not None else None


def _record_value_frequencies(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    table_name: str,
    column_name: str,
    row_count: int,
    approximate_distinct_count: int | None,
) -> None:
    """Persist the most frequent values for a low-cardinality column."""

    if (
        approximate_distinct_count is None
        or approximate_distinct_count > MAX_DISTINCT_VALUES_FOR_FREQUENCY_PROFILE
    ):
        return

    table = f"raw.{quote_identifier(table_name)}"
    column = quote_identifier(column_name)
    frequencies = connection.execute(
        f"""--sql
        SELECT {column}, count(*) AS value_count
        FROM {table}
        WHERE {column} IS NOT NULL
        GROUP BY {column}
        ORDER BY value_count DESC, {column}
        LIMIT {FREQUENCY_PROFILE_LIMIT}
        """
    ).fetchall()
    if not frequencies:
        return

    connection.executemany(
        """--sql
        INSERT INTO audit.value_profiles (
            run_id,
            table_name,
            column_name,
            value,
            value_count,
            value_rate
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            [
                run_id,
                table_name,
                column_name,
                value,
                value_count,
                value_count / row_count if row_count else 0,
            ]
            for value, value_count in frequencies
        ],
    )


def collect_source_statistics(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
) -> ColumnsByTable:
    """Persist descriptive statistics for every raw table and column."""

    columns_by_table = list_raw_columns(connection)
    for table_name, columns in columns_by_table.items():
        row_count = _record_table_statistics(connection, run_id, table_name, len(columns))
        for column_name, data_type in columns:
            approximate_distinct_count = _record_column_statistics(
                connection,
                run_id,
                table_name,
                column_name,
                data_type,
            )
            _record_value_frequencies(
                connection,
                run_id,
                table_name,
                column_name,
                row_count,
                approximate_distinct_count,
            )
    return columns_by_table


def measure_type_compatibility(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    available_columns: ColumnsByTable,
    staging_types: StagingTypes,
) -> None:
    """Measure whether selected raw VARCHAR columns support proposed staging types."""

    available = {
        (table_name, column_name)
        for table_name, columns in available_columns.items()
        for column_name, _ in columns
    }

    for (table_name, column_name), target_type in staging_types.items():
        if (table_name, column_name) not in available:
            continue

        table = f"raw.{quote_identifier(table_name)}"
        column = quote_identifier(column_name)
        result = connection.execute(
            f"""--sql
            WITH typed AS (
                SELECT
                    nullif(trim({column}), '') AS source_value,
                    try_cast(nullif(trim({column}), '') AS {target_type}) AS typed_value
                FROM {table}
            )
            SELECT
                count(*) FILTER (WHERE source_value IS NOT NULL) AS populated_count,
                count(*) FILTER (WHERE typed_value IS NOT NULL) AS valid_count,
                count(*) FILTER (
                    WHERE source_value IS NOT NULL AND typed_value IS NULL
                ) AS invalid_count,
                min(typed_value)::VARCHAR AS minimum_value,
                max(typed_value)::VARCHAR AS maximum_value
            FROM typed
            """
        ).fetchone()
        assert result is not None
        connection.execute(
            """--sql
            INSERT INTO audit.type_profiles (
                run_id,
                table_name,
                column_name,
                target_type,
                populated_count,
                valid_count,
                invalid_count,
                minimum_value,
                maximum_value
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [run_id, table_name, column_name, target_type, *result],
        )
