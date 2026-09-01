"""Olist checkout paths.

This module lives at ``src/olist/paths.py``. The default root is two parents
above that file. Set ``OLIST_PROJECT_ROOT`` when the process is not running
from this layout (tests, a copied tree). ``common`` does not locate the repo.
"""

import os
from pathlib import Path



def project_root() -> Path:
    configured = os.environ.get("OLIST_PROJECT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


WAREHOUSE_PATH = project_root() / "data" / "warehouse" / "olist.duckdb"
