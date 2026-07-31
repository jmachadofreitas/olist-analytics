from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import duckdb

from olist.paths import WAREHOUSE_PATH
from olist.profiling.checks import run_checks
from olist.profiling.stats import collect_source_statistics, measure_type_compatibility
from olist.warehouse import connect


@dataclass
class ProfilingResult:
    """Summarize a completed profiling run for CLI and orchestration callers."""

    run_id: str
    table_count: int
    failed_check_count: int


AUDIT_SCHEMA_SQL = """--sql
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.profile_runs (
    run_id VARCHAR PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR NOT NULL,
    source_schema VARCHAR NOT NULL,
    error_message VARCHAR
);

CREATE TABLE IF NOT EXISTS audit.table_profiles (
    run_id VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,
    row_count BIGINT NOT NULL,
    column_count INTEGER NOT NULL,
    PRIMARY KEY (run_id, table_name)
);

CREATE TABLE IF NOT EXISTS audit.column_profiles (
    run_id VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,
    column_name VARCHAR NOT NULL,
    data_type VARCHAR NOT NULL,
    row_count BIGINT NOT NULL,
    null_count BIGINT NOT NULL,
    empty_count BIGINT NOT NULL,
    approximate_distinct_count BIGINT,
    minimum_value VARCHAR,
    maximum_value VARCHAR,
    minimum_length BIGINT,
    maximum_length BIGINT,
    PRIMARY KEY (run_id, table_name, column_name)
);

CREATE TABLE IF NOT EXISTS audit.value_profiles (
    run_id VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,
    column_name VARCHAR NOT NULL,
    value VARCHAR,
    value_count BIGINT NOT NULL,
    value_rate DOUBLE NOT NULL
);

CREATE TABLE IF NOT EXISTS audit.type_profiles (
    run_id VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,
    column_name VARCHAR NOT NULL,
    target_type VARCHAR NOT NULL,
    populated_count BIGINT NOT NULL,
    valid_count BIGINT NOT NULL,
    invalid_count BIGINT NOT NULL,
    minimum_value VARCHAR,
    maximum_value VARCHAR,
    PRIMARY KEY (run_id, table_name, column_name, target_type)
);

CREATE TABLE IF NOT EXISTS audit.check_results (
    run_id VARCHAR NOT NULL,
    check_name VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    affected_rows BIGINT,
    total_rows BIGINT,
    affected_rate DOUBLE,
    description VARCHAR NOT NULL,
    PRIMARY KEY (run_id, check_name)
);
"""


def _ensure_raw_schema(connection: duckdb.DuckDBPyConnection) -> None:
    raw_table_count = connection.execute(
        """--sql
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'raw'
        """
    ).fetchone()
    if raw_table_count is None or raw_table_count[0] == 0:
        raise RuntimeError("No raw tables found; run ingestion before profiling")


def profile_raw_sources(
    warehouse_path: Path = WAREHOUSE_PATH,
) -> ProfilingResult:
    """Profile the raw schema and persist a historical audit run."""

    run_id = str(uuid4())
    connection = connect(warehouse_path)

    try:
        connection.execute(AUDIT_SCHEMA_SQL)
        _ensure_raw_schema(connection)
        connection.execute(
            """--sql
            INSERT INTO audit.profile_runs (
                run_id,
                started_at,
                completed_at,
                status,
                source_schema,
                error_message
            )
            VALUES (?, current_timestamp, NULL, 'running', 'raw', NULL)
            """,
            [run_id],
        )

        connection.execute("BEGIN TRANSACTION")
        columns = collect_source_statistics(connection, run_id)
        measure_type_compatibility(connection, run_id, columns)
        run_checks(connection, run_id, columns)
        connection.execute("COMMIT")

        connection.execute(
            """--sql
            UPDATE audit.profile_runs
            SET completed_at = current_timestamp, status = 'completed'
            WHERE run_id = ?
            """,
            [run_id],
        )

        table_count = connection.execute(
            "SELECT count(*) FROM audit.table_profiles WHERE run_id = ?",
            [run_id],
        ).fetchone()
        failed_check_count = connection.execute(
            """--sql
            SELECT count(*)
            FROM audit.check_results
            WHERE run_id = ? AND status = 'failed'
            """,
            [run_id],
        ).fetchone()
        assert table_count is not None and failed_check_count is not None
        return ProfilingResult(
            run_id=run_id,
            table_count=table_count[0],
            failed_check_count=failed_check_count[0],
        )
    except Exception as error:
        try:
            connection.execute("ROLLBACK")
        except duckdb.TransactionException:
            pass
        connection.execute(
            """--sql
            UPDATE audit.profile_runs
            SET completed_at = current_timestamp,
                status = 'failed',
                error_message = ?
            WHERE run_id = ?
            """,
            [str(error), run_id],
        )
        raise
    finally:
        connection.close()
