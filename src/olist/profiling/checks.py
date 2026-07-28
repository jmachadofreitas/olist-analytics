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
