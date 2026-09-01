from pathlib import Path

import duckdb

from olist.ingestion import SOURCE_TABLES, load_raw_data


def _write_sources(raw_data_dir: Path, value: str = "first") -> None:
    for relative_path in SOURCE_TABLES:
        path = raw_data_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"id,value\n1,{value}\n", encoding="utf-8")


def test_loads_all_source_files_into_raw_schema(tmp_path: Path) -> None:
    raw_data_dir = tmp_path / "raw"
    warehouse_path = tmp_path / "warehouse" / "olist.duckdb"
    _write_sources(raw_data_dir)

    results = load_raw_data(raw_data_dir, warehouse_path)

    assert {result.table for result in results} == set(SOURCE_TABLES.values())
    assert all(result.rows == 1 for result in results)

    with duckdb.connect(str(warehouse_path)) as connection:
        row = connection.execute(
            "SELECT id, value, _source_file, _loaded_at FROM raw.orders"
        ).fetchone()
        column_type = connection.execute(
            """--sql
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'raw'
              AND table_name = 'orders'
              AND column_name = 'id'
            """
        ).fetchone()

    assert row is not None
    assert row[:3] == ("1", "first", "ecommerce/olist_orders_dataset.csv")
    assert row[3] is not None
    assert column_type == ("VARCHAR",)


def test_replaces_raw_tables_on_each_load(tmp_path: Path) -> None:
    raw_data_dir = tmp_path / "raw"
    warehouse_path = tmp_path / "warehouse" / "olist.duckdb"
    _write_sources(raw_data_dir)
    load_raw_data(raw_data_dir, warehouse_path)

    _write_sources(raw_data_dir, value="second")
    load_raw_data(raw_data_dir, warehouse_path)

    with duckdb.connect(str(warehouse_path)) as connection:
        rows = connection.execute("SELECT id, value FROM raw.orders").fetchall()

    assert rows == [("1", "second")]
