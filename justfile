default:
    @just --list

download:
    ./scripts/download_data.sh

ingest:
    uv run python -m olist ingest

profile:
    uv run python -m olist profile

dbt model="":
    uv run dbt build --project-dir dbt/olist --profiles-dir dbt/olist {{ if model == "" { "" } else { "--select " + quote(model) } }}

dbt-test model="":
    uv run dbt test --project-dir dbt/olist --profiles-dir dbt/olist {{ if model == "" { "" } else { "--select " + quote(model) } }}

dbt-debug:
    uv run dbt debug --project-dir dbt/olist --profiles-dir dbt/olist

lint:
    uv run ruff check .

test:
    uv run pytest

check: lint test
