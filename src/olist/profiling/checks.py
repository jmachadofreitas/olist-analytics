"""Define and run Olist-specific source quality checks.

> Does the raw source contradict an explicit expectation?
"""

from dataclasses import dataclass
from enum import StrEnum

import duckdb


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
    """Check whether any required key column is null or empty."""

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
    """Check a candidate key for duplicate rows."""
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

def _key_checks() -> list[CheckSpec]:
    """Build and return checks that validate the candidate source keys of each raw table."""
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

