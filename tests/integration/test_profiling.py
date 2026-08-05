from pathlib import Path

import duckdb
import pytest

from olist.profiling import ProfilingResult, profile_raw_sources


def _create_profile_sources(warehouse_path: Path) -> None:
    with duckdb.connect(str(warehouse_path)) as connection:
        connection.execute("CREATE SCHEMA raw")
        connection.execute(
            """--sql
            CREATE TABLE raw.customers AS
            SELECT *
            FROM (VALUES
                ('customer-1', 'person-1'),
                ('customer-1', 'person-1'),
                ('', 'person-2')
            ) AS source(customer_id, customer_unique_id)
            """
        )
        connection.execute(
            """--sql
            CREATE TABLE raw.orders AS
            SELECT *
            FROM (VALUES
                ('order-1', 'customer-1', '2018-01-01 10:00:00', '2018-01-01 11:00:00'),
                ('order-2', 'missing-customer', '2018-01-02 10:00:00', 'invalid')
            ) AS source(
                order_id,
                customer_id,
                order_purchase_timestamp,
                order_approved_at
            )
            """
        )


def _add_malformed_source(warehouse_path: Path) -> None:
    with duckdb.connect(str(warehouse_path)) as connection:
        connection.execute("CREATE TABLE raw.malformed (value INTEGER)")
        connection.execute("INSERT INTO raw.malformed VALUES (1)")


@pytest.fixture
def profiled_sources(tmp_path: Path) -> tuple[Path, Path, ProfilingResult]:
    warehouse_path = tmp_path / "warehouse.duckdb"
    report_path = tmp_path / "source-profile.md"
    _create_profile_sources(warehouse_path)
    result = profile_raw_sources(warehouse_path, report_path)
    return warehouse_path, report_path, result


def test_completes_profile_run_and_writes_report(
    profiled_sources: tuple[Path, Path, ProfilingResult],
) -> None:
    warehouse_path, report_path, result = profiled_sources

    with duckdb.connect(str(warehouse_path)) as connection:
        run_status = connection.execute(
            "SELECT status FROM audit.profile_runs WHERE run_id = ?",
            [result.run_id],
        ).fetchone()

    assert result.table_count == 2
    assert result.failed_check_count == 3
    assert run_status == ("completed",)
    assert report_path.exists()
    assert "## Table inventory" in report_path.read_text(encoding="utf-8")


def test_records_descriptive_and_type_profiles(
    profiled_sources: tuple[Path, Path, ProfilingResult],
) -> None:
    warehouse_path, _, result = profiled_sources

    with duckdb.connect(str(warehouse_path)) as connection:
        table_statistics = connection.execute(
            """--sql
            SELECT row_count, column_count
            FROM audit.table_profiles
            WHERE run_id = ? AND table_name = 'orders'
            """,
            [result.run_id],
        ).fetchone()
        column_statistics = connection.execute(
            """--sql
            SELECT row_count, null_count, empty_count
            FROM audit.column_profiles
            WHERE run_id = ?
              AND table_name = 'orders'
              AND column_name = 'order_approved_at'
            """,
            [result.run_id],
        ).fetchone()
        common_values = connection.execute(
            """--sql
            SELECT value, value_count, value_rate
            FROM audit.value_profiles
            WHERE run_id = ?
              AND table_name = 'orders'
              AND column_name = 'order_approved_at'
            ORDER BY value
            """,
            [result.run_id],
        ).fetchall()
        type_profile = connection.execute(
            """--sql
            SELECT target_type, populated_count, valid_count, invalid_count
            FROM audit.type_profiles
            WHERE run_id = ?
              AND table_name = 'orders'
              AND column_name = 'order_approved_at'
            """,
            [result.run_id],
        ).fetchone()

    assert table_statistics == (2, 4)
    assert column_statistics == (2, 0, 0)
    assert common_values == [
        ("2018-01-01 11:00:00", 1, 0.5),
        ("invalid", 1, 0.5),
    ]
    assert type_profile == ("TIMESTAMP", 2, 1, 1)


def test_classifies_failures_observations_and_skips(
    profiled_sources: tuple[Path, Path, ProfilingResult],
) -> None:
    warehouse_path, _, result = profiled_sources

    with duckdb.connect(str(warehouse_path)) as connection:
        rows = connection.execute(
            """--sql
            SELECT
                check_name,
                category,
                status,
                affected_rows,
                total_rows,
                affected_rate
            FROM audit.check_results
            WHERE run_id = ?
              AND check_name IN (
                  'customers_customer_id_not_null',
                  'customers_customer_id_unique',
                  'orders_customer_id_references_customers',
                  'customers_with_repeated_unique_ids',
                  'products_product_id_unique'
              )
            """,
            [result.run_id],
        ).fetchall()

    checks = {row[0]: row[1:] for row in rows}
    assert checks["customers_customer_id_not_null"] == (
        "completeness",
        "failed",
        1,
        3,
        pytest.approx(1 / 3),
    )
    assert checks["customers_customer_id_unique"] == (
        "uniqueness",
        "failed",
        1,
        3,
        pytest.approx(1 / 3),
    )
    assert checks["orders_customer_id_references_customers"] == (
        "integrity",
        "failed",
        1,
        2,
        pytest.approx(1 / 2),
    )
    assert checks["customers_with_repeated_unique_ids"] == (
        "cardinality",
        "observed",
        1,
        3,
        pytest.approx(1 / 3),
    )
    assert checks["products_product_id_unique"] == (
        "uniqueness",
        "skipped",
        None,
        None,
        None,
    )


def test_failed_profile_run_is_atomic(tmp_path: Path) -> None:
    warehouse_path = tmp_path / "warehouse.duckdb"
    report_path = tmp_path / "source-profile.md"

    with duckdb.connect(str(warehouse_path)) as connection:
        connection.execute("CREATE SCHEMA raw")
    _add_malformed_source(warehouse_path)

    with pytest.raises(duckdb.BinderException):
        profile_raw_sources(warehouse_path, report_path)

    with duckdb.connect(str(warehouse_path)) as connection:
        run = connection.execute(
            "SELECT status, error_message FROM audit.profile_runs"
        ).fetchone()
        stored_results = connection.execute(
            """--sql
            SELECT
                (SELECT count(*) FROM audit.table_profiles),
                (SELECT count(*) FROM audit.column_profiles),
                (SELECT count(*) FROM audit.check_results)
            """
        ).fetchone()

    assert run is not None
    assert run[0] == "failed"
    assert run[1]
    assert stored_results == (0, 0, 0)
    assert not report_path.exists()


def test_report_compares_with_previous_completed_run(tmp_path: Path) -> None:
    warehouse_path = tmp_path / "warehouse.duckdb"
    report_path = tmp_path / "source-profile.md"

    with duckdb.connect(str(warehouse_path)) as connection:
        connection.execute("CREATE SCHEMA raw")
        connection.execute(
            """--sql
            CREATE TABLE raw.customers AS
            SELECT 'customer-1' AS customer_id, 'person-1' AS customer_unique_id
            """
        )

    profile_raw_sources(warehouse_path, report_path)
    _add_malformed_source(warehouse_path)

    with pytest.raises(duckdb.BinderException):
        profile_raw_sources(warehouse_path, report_path)

    with duckdb.connect(str(warehouse_path)) as connection:
        connection.execute("DROP TABLE raw.malformed")
        connection.execute(
            "INSERT INTO raw.customers VALUES ('customer-2', 'person-2')"
        )

    profile_raw_sources(warehouse_path, report_path)

    report = report_path.read_text(encoding="utf-8")
    assert "| `customers` | 2 | 2 | 1 | +1 |" in report
