"""Define and run Olist-specific source quality checks.

> Does the raw source contradict an explicit expectation?
"""

from dataclasses import dataclass
from enum import StrEnum

import duckdb

from olist.warehouse import quote_identifier


class CheckCategory(StrEnum):
    """Group checks by the primary analytical risk they assess.

    CARDINALITY: Relationship multiplicity that may multiply rows in joins.
    COMPLETENESS: Missing required records or values.
    CONSISTENCY: Contradictory values or event sequences.
    GRAIN: Rows that do not match the declared unit of analysis.
    INTEGRITY: References that do not resolve to existing records.
    UNIQUENESS: Duplicate candidate-key values.
    VALIDITY: Values outside an expected type, format, domain, or range.
    """

    CARDINALITY = "cardinality"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    GRAIN = "grain"
    INTEGRITY = "integrity"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"


@dataclass
class CheckSpec:
    """Describe one SQL check and the source columns it requires."""

    name: str
    category: CheckCategory
    description: str
    query: str
    requirements: set[tuple[str, str]]
    enforced: bool = True


def _not_null(
    table_name: str,
    columns: tuple[str, ...],
) -> CheckSpec:
    """Count rows where any selected column is null or blank."""

    table = f"raw.{quote_identifier(table_name)}"
    predicate = " OR ".join(
        f"nullif(trim({quote_identifier(column)}), '') IS NULL" for column in columns
    )
    label = "_and_".join(columns)
    return CheckSpec(
        name=f"{table_name}_{label}_not_null",
        category=CheckCategory.COMPLETENESS,
        description=f"Required key columns on raw.{table_name} should be populated.",
        query=f"SELECT count_if({predicate}), count(*) FROM {table}",
        requirements={(table_name, column) for column in columns},
    )


def _unique(
    table_name: str,
    columns: tuple[str, ...],
) -> CheckSpec:
    """Count extra rows in groups that share the same key."""
    table = f"raw.{quote_identifier(table_name)}"
    keys = ", ".join(quote_identifier(column) for column in columns)
    label = "_and_".join(columns)
    return CheckSpec(
        name=f"{table_name}_{label}_unique",
        category=CheckCategory.UNIQUENESS,
        description=f"The candidate grain of raw.{table_name} should be unique.",
        query=f"""--sql
            WITH duplicate_keys AS (
                SELECT count(*) AS occurrences
                FROM {table}
                GROUP BY {keys}
                HAVING count(*) > 1
            )
            SELECT
                coalesce(sum(occurrences - 1), 0)::BIGINT,
                (SELECT count(*) FROM {table})
            FROM duplicate_keys
        """,
        requirements={(table_name, column) for column in columns},
    )


def _orphan(
    child_table: str,
    child_column: str,
    parent_table: str,
    parent_column: str,
    *,
    enforced: bool = True,
) -> CheckSpec:
    """Count rows whose non-empty foreign key has no match in the referenced table."""
    child = quote_identifier(child_table)
    parent = quote_identifier(parent_table)
    child_key = quote_identifier(child_column)
    parent_key = quote_identifier(parent_column)
    return CheckSpec(
        name=f"{child_table}_{child_column}_references_{parent_table}",
        category=CheckCategory.INTEGRITY,
        description=(
            f"Populated raw.{child_table}.{child_column} values should match "
            f"raw.{parent_table}.{parent_column}."
        ),
        query=f"""--sql
            SELECT
                count(*) FILTER (
                    WHERE child.{child_key} IS NOT NULL
                      AND trim(child.{child_key}) <> ''
                      AND NOT EXISTS (
                          SELECT 1
                          FROM raw.{parent} AS parent
                          WHERE parent.{parent_key} = child.{child_key}
                      )
                ),
                count(*) FILTER (
                    WHERE child.{child_key} IS NOT NULL
                      AND trim(child.{child_key}) <> ''
                )
            FROM raw.{child} AS child
        """,
        requirements={(child_table, child_column), (parent_table, parent_column)},
        enforced=enforced,
    )


def _order_timestamp_order(
    name: str,
    earlier_column: str,
    later_column: str,
) -> CheckSpec:
    """Count order rows where two valid timestamps occur in the wrong order."""
    earlier = quote_identifier(earlier_column)
    later = quote_identifier(later_column)
    return CheckSpec(
        name=name,
        category=CheckCategory.CONSISTENCY,
        description=f"{later_column} should not precede {earlier_column}.",
        query=f"""--sql
            SELECT
                count(*) FILTER (
                    WHERE try_cast({later} AS TIMESTAMP)
                        < try_cast({earlier} AS TIMESTAMP)
                ),
                count(*) FILTER (
                    WHERE try_cast({later} AS TIMESTAMP) IS NOT NULL
                      AND try_cast({earlier} AS TIMESTAMP) IS NOT NULL
                )
            FROM raw.orders
        """,
        requirements={("orders", earlier_column), ("orders", later_column)},
    )


def _non_negative(
    name: str,
    table_name: str,
    columns: tuple[str, ...],
    description: str,
) -> CheckSpec:
    """Count rows where any selected value parses as a negative decimal."""
    table = f"raw.{quote_identifier(table_name)}"
    predicate = " OR ".join(
        f"try_cast({quote_identifier(column)} AS DECIMAL(18, 2)) < 0" for column in columns
    )
    return CheckSpec(
        name=name,
        category=CheckCategory.VALIDITY,
        description=description,
        query=f"SELECT count_if({predicate}), count(*) FROM {table}",
        requirements={(table_name, column) for column in columns},
    )


def _repeated_values(
    name: str,
    table_name: str,
    column_name: str,
    description: str,
) -> CheckSpec:
    """Count extra occurrences of each repeated non-null value."""
    table = f"raw.{quote_identifier(table_name)}"
    column = quote_identifier(column_name)
    return CheckSpec(
        name=name,
        category=CheckCategory.CARDINALITY,
        description=description,
        query=f"""--sql
            WITH repeated AS (
                SELECT count(*) AS occurrences
                FROM {table}
                WHERE {column} IS NOT NULL
                GROUP BY {column}
                HAVING count(*) > 1
            )
            SELECT
                coalesce(sum(occurrences - 1), 0)::BIGINT,
                (SELECT count(*) FROM {table} WHERE {column} IS NOT NULL)
            FROM repeated
        """,
        requirements={(table_name, column_name)},
        enforced=False,
    )


def _order_payment_reconciliation() -> CheckSpec:
    """
    Sum item price, freight, and payments by order, then count matched orders
    whose totals differ by more than 0.01.
    """
    return CheckSpec(
        name="orders_item_and_payment_value_reconciliation",
        category=CheckCategory.CONSISTENCY,
        description=(
            "Aggregated item price plus freight is compared with payment value per order."
        ),
        query="""--sql
            WITH item_values AS (
                SELECT
                    order_id,
                    sum(try_cast(price AS DECIMAL(18, 2)))
                    + sum(try_cast(freight_value AS DECIMAL(18, 2))) AS item_value
                FROM raw.order_items
                GROUP BY order_id
            ),
            payment_values AS (
                SELECT
                    order_id,
                    sum(try_cast(payment_value AS DECIMAL(18, 2))) AS payment_value
                FROM raw.order_payments
                GROUP BY order_id
            )
            SELECT
                count(*) FILTER (WHERE abs(item_value - payment_value) > 0.01),
                count(*)
            FROM item_values
            INNER JOIN payment_values USING (order_id)
        """,
        requirements={
            ("order_items", "order_id"),
            ("order_items", "price"),
            ("order_items", "freight_value"),
            ("order_payments", "order_id"),
            ("order_payments", "payment_value"),
        },
        enforced=False,
    )


def _key_checks() -> list[CheckSpec]:
    """Create completeness and uniqueness checks for each candidate source key."""
    candidates = [
        ("customers", ("customer_id",)),
        ("orders", ("order_id",)),
        ("products", ("product_id",)),
        ("sellers", ("seller_id",)),
        ("marketing_qualified_leads", ("mql_id",)),
        ("closed_deals", ("mql_id",)),
        ("order_items", ("order_id", "order_item_id")),
        ("order_payments", ("order_id", "payment_sequential")),
        (
            "product_category_name_translation",
            ("product_category_name",),
        ),
    ]
    return [
        check
        for table_name, columns in candidates
        for check in (
            _not_null(table_name, columns),
            _unique(table_name, columns),
        )
    ]


CHECKS = [
    *_key_checks(),
    _orphan(
        "orders",
        "customer_id",
        "customers",
        "customer_id",
    ),
    _orphan("order_items", "order_id", "orders", "order_id"),
    _orphan("order_items", "product_id", "products", "product_id"),
    _orphan("order_items", "seller_id", "sellers", "seller_id"),
    _orphan("order_payments", "order_id", "orders", "order_id"),
    _orphan("order_reviews", "order_id", "orders", "order_id"),
    _orphan(
        "products",
        "product_category_name",
        "product_category_name_translation",
        "product_category_name",
        enforced=False,
    ),
    _orphan(
        "closed_deals",
        "mql_id",
        "marketing_qualified_leads",
        "mql_id",
    ),
    _orphan(
        "closed_deals",
        "seller_id",
        "sellers",
        "seller_id",
        enforced=False,
    ),
    _order_timestamp_order(
        "orders_approval_not_before_purchase",
        "order_purchase_timestamp",
        "order_approved_at",
    ),
    _order_timestamp_order(
        "orders_carrier_handoff_not_before_approval",
        "order_approved_at",
        "order_delivered_carrier_date",
    ),
    _order_timestamp_order(
        "orders_customer_delivery_not_before_carrier_handoff",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
    ),
    _non_negative(
        "order_items_non_negative_values",
        "order_items",
        ("price", "freight_value"),
        "Item price and freight values should not be negative.",
    ),
    _non_negative(
        "order_payments_non_negative_value",
        "order_payments",
        ("payment_value",),
        "Payment values should not be negative.",
    ),
    _order_payment_reconciliation(),
    _repeated_values(
        "orders_with_multiple_reviews",
        "order_reviews",
        "order_id",
        "Orders with multiple review rows affect review-to-order joins.",
    ),
    _repeated_values(
        "closed_deals_with_repeated_sellers",
        "closed_deals",
        "seller_id",
        "Repeated sellers in closed deals affect seller-attribution joins.",
    ),
    _repeated_values(
        "customers_with_repeated_unique_ids",
        "customers",
        "customer_unique_id",
        "Repeated customer_unique_id values reveal repeat customer records.",
    ),
]


def run_checks(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    available_columns: dict[str, list[tuple[str, str]]],
) -> None:
    """
    Run checks whose required columns exist and store their results.
    Mark checks with missing required columns as skipped.
    """

    available = {
        (table_name, column_name)
        for table_name, columns in available_columns.items()
        for column_name, _ in columns
    }

    for check in CHECKS:
        if not check.requirements.issubset(available):
            connection.execute(
                """--sql
                INSERT INTO audit.check_results (
                    run_id,
                    check_name,
                    category,
                    status,
                    affected_rows,
                    total_rows,
                    affected_rate,
                    description
                )
                VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?)
                """,
                [
                    run_id,
                    check.name,
                    check.category.value,
                    "skipped",
                    check.description,
                ],
            )
            continue

        result = connection.execute(check.query).fetchone()
        assert result is not None
        affected_rows, total_rows = result
        affected_rows = int(affected_rows or 0)
        total_rows = int(total_rows or 0)
        affected_rate = affected_rows / total_rows if total_rows else 0.0
        if not check.enforced:
            status = "observed"
        else:
            status = "passed" if affected_rows == 0 else "failed"
        connection.execute(
            """--sql
            INSERT INTO audit.check_results (
                run_id,
                check_name,
                category,
                status,
                affected_rows,
                total_rows,
                affected_rate,
                description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                check.name,
                check.category.value,
                status,
                affected_rows,
                total_rows,
                affected_rate,
                check.description,
            ],
        )
