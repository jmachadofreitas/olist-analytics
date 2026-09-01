"""Olist raw-source quality checks. Table and column names belong here."""

from common.validation.checks import (
    CheckCategory,
    CheckSpec,
    non_negative,
    not_null,
    orphan,
    repeated_values,
    timestamp_order,
    unique,
)


def _key_checks() -> list[CheckSpec]:
    candidates = [
        ("customers", ("customer_id",)),
        ("orders", ("order_id",)),
        ("products", ("product_id",)),
        ("sellers", ("seller_id",)),
        ("marketing_qualified_leads", ("mql_id",)),
        ("closed_deals", ("mql_id",)),
        ("order_items", ("order_id", "order_item_id")),
        ("order_payments", ("order_id", "payment_sequential")),
        ("product_category_name_translation", ("product_category_name",)),
    ]
    return [
        check
        for table_name, columns in candidates
        for check in (not_null(table_name, columns), unique(table_name, columns))
    ]


def _order_payment_reconciliation() -> CheckSpec:
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


CHECKS = [
    *_key_checks(),
    orphan("orders", "customer_id", "customers", "customer_id"),
    orphan("order_items", "order_id", "orders", "order_id"),
    orphan("order_items", "product_id", "products", "product_id"),
    orphan("order_items", "seller_id", "sellers", "seller_id"),
    orphan("order_payments", "order_id", "orders", "order_id"),
    orphan("order_reviews", "order_id", "orders", "order_id"),
    orphan(
        "products",
        "product_category_name",
        "product_category_name_translation",
        "product_category_name",
        enforced=False,
    ),
    orphan("closed_deals", "mql_id", "marketing_qualified_leads", "mql_id"),
    orphan("closed_deals", "seller_id", "sellers", "seller_id", enforced=False),
    timestamp_order(
        "orders_approval_not_before_purchase",
        "orders",
        "order_purchase_timestamp",
        "order_approved_at",
    ),
    timestamp_order(
        "orders_carrier_handoff_not_before_approval",
        "orders",
        "order_approved_at",
        "order_delivered_carrier_date",
        enforced=False,
    ),
    timestamp_order(
        "orders_customer_delivery_not_before_carrier_handoff",
        "orders",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        enforced=False,
    ),
    non_negative(
        "order_items_non_negative_values",
        "order_items",
        ("price", "freight_value"),
        "Item price and freight values should not be negative.",
    ),
    non_negative(
        "order_payments_non_negative_value",
        "order_payments",
        ("payment_value",),
        "Payment values should not be negative.",
    ),
    _order_payment_reconciliation(),
    repeated_values(
        "orders_with_multiple_reviews",
        "order_reviews",
        "order_id",
        "Orders with multiple review rows affect review-to-order joins.",
    ),
    repeated_values(
        "closed_deals_with_repeated_sellers",
        "closed_deals",
        "seller_id",
        "Repeated sellers in closed deals affect seller-attribution joins.",
    ),
    repeated_values(
        "customers_with_repeated_unique_ids",
        "customers",
        "customer_unique_id",
        "Repeated customer_unique_id values reveal repeat customer records.",
    ),
]
