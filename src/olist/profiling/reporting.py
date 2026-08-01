"""Render a stored profiling run as Markdown."""

from datetime import datetime
from pathlib import Path

import duckdb

type RunSummary = tuple[datetime, datetime | None, str]
type TableProfile = tuple[str, int, int, int | None]
type CheckResult = tuple[str, str, str, int, float, str]
type TypeProfile = tuple[str, str, str, int, int, int, str | None, str | None]
type MissingnessProfile = tuple[str, str, int, int, float]


def _escape(value: object) -> str:
    if value is None:
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _rate(value: float | None) -> str:
    return "—" if value is None else f"{value:.2%}"


def _fetch_run_summary(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
) -> RunSummary:
    """Return the timestamps and status for one profiling run."""

    run = connection.execute(
        """--sql
        SELECT started_at, completed_at, status
        FROM audit.profile_runs
        WHERE run_id = ?
        """,
        [run_id],
    ).fetchone()
    assert run is not None
    return run


def _fetch_table_profiles(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
) -> list[TableProfile]:
    """Return table statistics with row counts from the previous completed run."""

    return connection.execute(
        """--sql
        WITH previous_run AS (
            SELECT run_id
            FROM audit.profile_runs
            WHERE status = 'completed' AND run_id <> ?
            ORDER BY completed_at DESC
            LIMIT 1
        )
        SELECT
            current.table_name,
            current.row_count,
            current.column_count,
            previous.row_count AS previous_row_count
        FROM audit.table_profiles AS current
        LEFT JOIN audit.table_profiles AS previous
          ON previous.run_id = (SELECT run_id FROM previous_run)
         AND previous.table_name = current.table_name
        WHERE current.run_id = ?
        ORDER BY current.table_name
        """,
        [run_id, run_id],
    ).fetchall()


def _fetch_check_results(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
) -> list[CheckResult]:
    """Return failed expectations and non-enforced observations."""

    return connection.execute(
        """--sql
        SELECT
            check_name,
            category,
            status,
            affected_rows,
            affected_rate,
            description
        FROM audit.check_results
        WHERE run_id = ? AND status IN ('failed', 'observed')
        ORDER BY category, check_name
        """,
        [run_id],
    ).fetchall()


def _fetch_check_counts(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
) -> dict[str, int]:
    """Return the number of checks in each status."""

    rows = connection.execute(
        """--sql
        SELECT status, count(*)
        FROM audit.check_results
        WHERE run_id = ?
        GROUP BY status
        """,
        [run_id],
    ).fetchall()
    return dict(rows)


def _fetch_type_profiles(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
) -> list[TypeProfile]:
    """Return compatibility statistics for proposed staging types."""

    return connection.execute(
        """--sql
        SELECT
            table_name,
            column_name,
            target_type,
            populated_count,
            valid_count,
            invalid_count,
            minimum_value,
            maximum_value
        FROM audit.type_profiles
        WHERE run_id = ?
        ORDER BY invalid_count DESC, table_name, column_name
        """,
        [run_id],
    ).fetchall()


def _fetch_missingness_profiles(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
) -> list[MissingnessProfile]:
    """Return the 30 columns with the highest nonzero missing rates."""

    return connection.execute(
        """--sql
        SELECT
            table_name,
            column_name,
            null_count,
            empty_count,
            (null_count + empty_count)::DOUBLE / nullif(row_count, 0) AS missing_rate
        FROM audit.column_profiles
        WHERE run_id = ? AND null_count + empty_count > 0
        ORDER BY missing_rate DESC, table_name, column_name
        LIMIT 30
        """,
        [run_id],
    ).fetchall()

