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


def _render_header(
    run_id: str,
    run: RunSummary,
    table_count: int,
    check_counts: dict[str, int],
    title: str,
) -> list[str]:
    """Render the report title and run summary."""

    return [
        f"# {title}",
        "",
        f"- Run ID: `{run_id}`",
        f"- Started: `{run[0]}`",
        f"- Completed: `{run[1]}`",
        f"- Status: `{run[2]}`",
        f"- Tables: {table_count}",
        f"- Failed checks: {check_counts.get('failed', 0)}",
        f"- Observations: {check_counts.get('observed', 0)}",
        f"- Skipped checks: {check_counts.get('skipped', 0)}",
    ]


def _render_table_inventory(tables: list[TableProfile]) -> list[str]:
    """Render table sizes and changes from the previous profiling run."""

    lines = [
        "",
        "## Table inventory",
        "",
        "| Table | Rows | Columns | Previous rows | Change |",
        "|---|---:|---:|---:|---:|",
    ]
    for table_name, row_count, column_count, previous_row_count in tables:
        change = "—" if previous_row_count is None else f"{row_count - previous_row_count:+,}"
        previous = "—" if previous_row_count is None else f"{previous_row_count:,}"
        lines.append(f"| `{table_name}` | {row_count:,} | {column_count} | {previous} | {change} |")
    return lines


def _render_check_sections(checks: list[CheckResult]) -> list[str]:
    """Render failed expectations and non-enforced observations."""

    failed_checks = [check for check in checks if check[2] == "failed"]
    observed_checks = [check for check in checks if check[2] == "observed"]
    lines = [
        "",
        "## Failed expectations",
        "",
        "| Check | Category | Affected | Rate | Why it matters |",
        "|---|---|---:|---:|---|",
    ]
    if not failed_checks:
        lines.append("| None | — | — | — | No configured expectation failed. |")
    for name, category, _, affected, rate, description in failed_checks:
        lines.append(
            f"| `{name}` | {category} | {affected:,} | {_rate(rate)} | {_escape(description)} |"
        )

    lines.extend(
        [
            "",
            "## Profiling observations",
            "",
            "Observations describe source behavior and are not yet enforced expectations.",
            "",
            "| Check | Category | Affected | Rate | Interpretation |",
            "|---|---|---:|---:|---|",
        ]
    )
    if not observed_checks:
        lines.append("| None | — | — | — | No observations were configured. |")
    for name, category, _, affected, rate, description in observed_checks:
        lines.append(
            f"| `{name}` | {category} | {affected:,} | {_rate(rate)} | {_escape(description)} |"
        )
    return lines


def _render_type_compatibility(types: list[TypeProfile]) -> list[str]:
    """Render compatibility statistics for proposed staging types."""

    lines = [
        "",
        "## Type compatibility",
        "",
        "Raw source columns are VARCHAR. These results measure proposed staging casts.",
        "",
        "| Column | Target type | Populated | Invalid | Valid rate | Range |",
        "|---|---|---:|---:|---:|---|",
    ]
    for table, column, target, populated, valid, invalid, minimum, maximum in types:
        valid_rate = valid / populated if populated else None
        value_range = f"{_escape(minimum)} to {_escape(maximum)}"
        lines.append(
            f"| `{table}.{column}` | `{target}` | {populated:,} | {invalid:,} | "
            f"{_rate(valid_rate)} | {value_range} |"
        )
    return lines


def _render_missingness(missingness: list[MissingnessProfile]) -> list[str]:
    """Render columns containing null or blank values."""

    lines = [
        "",
        "## Highest missingness",
        "",
        "| Column | Null | Empty | Missing rate |",
        "|---|---:|---:|---:|",
    ]
    if not missingness:
        lines.append("| None | 0 | 0 | 0.00% |")
    for table, column, nulls, empty, rate in missingness:
        lines.append(f"| `{table}.{column}` | {nulls:,} | {empty:,} | {_rate(rate)} |")
    return lines


def _render_interpretation_boundary() -> list[str]:
    """Render the boundary between source findings and accepted model rules."""

    return [
        "",
        "## Interpretation boundary",
        "",
        "This report establishes source behavior. Only checks marked as expectations are "
        "treated as failures. Observations require modeling decisions before becoming dbt "
        "tests or Dagster asset checks.",
        "",
    ]


def render_markdown_report(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    report_path: Path,
    *,
    title: str = "Raw-source profile",
) -> None:
    """Load one profiling run and write its Markdown report."""

    run = _fetch_run_summary(connection, run_id)
    tables = _fetch_table_profiles(connection, run_id)
    checks = _fetch_check_results(connection, run_id)
    check_counts = _fetch_check_counts(connection, run_id)
    types = _fetch_type_profiles(connection, run_id)
    missingness = _fetch_missingness_profiles(connection, run_id)

    lines = _render_header(run_id, run, len(tables), check_counts, title)
    lines.extend(_render_table_inventory(tables))
    lines.extend(_render_check_sections(checks))
    lines.extend(_render_type_compatibility(types))
    lines.extend(_render_missingness(missingness))
    lines.extend(_render_interpretation_boundary())

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
