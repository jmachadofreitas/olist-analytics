"""Project paths used by local ingestion and analytical storage."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
WAREHOUSE_PATH = PROJECT_ROOT / "data" / "warehouse" / "olist.duckdb"
