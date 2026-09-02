import duckdb
import polars as pl

from olist.analysis.types import (
    DeliveryPerformanceOverall,
    MonthlyDeliveryDifferenceDistribution,
    MonthlyDeliveryDifferenceOutliers,
    MonthlyDeliveryPerformance,
)


def _frame_from_query(connection: duckdb.DuckDBPyConnection, sql: str) -> pl.DataFrame:
    cursor = connection.execute(sql)
    description = cursor.description
    if description is None:
        raise RuntimeError("Query did not return a result description.")
    return pl.DataFrame(
        cursor.fetchall(),
        schema=[column[0] for column in description],
        orient="row",
    )


def monthly_delivery_performance(
    connection: duckdb.DuckDBPyConnection,
) -> MonthlyDeliveryPerformance:
    """Load the dbt-owned monthly delivery-performance aggregate."""
    return MonthlyDeliveryPerformance(
        _frame_from_query(
            connection,
            """--sql
            select *
            from main.agg_delivery_performance_monthly
            order by purchase_month
            """,
        )
    )


def monthly_delivery_difference_distribution(
    connection: duckdb.DuckDBPyConnection,
) -> MonthlyDeliveryDifferenceDistribution:
    """Load paired monthly delivery-date distribution statistics."""
    return MonthlyDeliveryDifferenceDistribution(
        _frame_from_query(
            connection,
            """--sql
            select *
            from main.agg_delivery_difference_monthly_comparison
            order by purchase_month_number, purchase_year
            """,
        )
    )


def monthly_delivery_difference_outliers(
    connection: duckdb.DuckDBPyConnection,
) -> MonthlyDeliveryDifferenceOutliers:
    """Load order-level delivery-date outlier and extreme classifications."""
    return MonthlyDeliveryDifferenceOutliers(
        _frame_from_query(
            connection,
            """--sql
            select *
            from main.fct_delivery_difference_outliers
            order by
                purchase_month_number,
                purchase_year,
                delivery_difference_days,
                order_id
            """,
        )
    )


def delivery_performance_overall(
    connection: duckdb.DuckDBPyConnection,
) -> DeliveryPerformanceOverall:
    """Load the dbt-owned one-row overall delivery-performance aggregate."""
    cursor = connection.execute(
        """--sql
        select
            eligible_delivered_orders,
            on_time_orders,
            on_time_delivery_rate_pct,
            average_delivery_difference_days,
            median_delivery_difference_days
        from main.agg_delivery_performance_overall
        """
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("agg_delivery_performance_overall returned no rows.")
    return DeliveryPerformanceOverall(
        eligible_delivered_orders=int(row[0]),
        on_time_orders=int(row[1]),
        on_time_delivery_rate_pct=float(row[2]),
        average_delivery_difference_days=float(row[3]),
        median_delivery_difference_days=float(row[4]),
    )
