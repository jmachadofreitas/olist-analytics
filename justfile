default:
    @just --list

activate:
    #!/usr/bin/env bash
    uv sync
    source .venv/bin/activate
    export VIRTUAL_ENV_PROMPT=olist
    exec bash -i
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

sqlfluff:
    uv run sqlfluff lint dbt

typecheck:
    uv run basedpyright

test:
    uv run pytest

check: lint sqlfluff typecheck test
