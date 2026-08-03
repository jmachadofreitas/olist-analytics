default:
    @just --list

download:
    ./scripts/download_data.sh

ingest:
    uv run python -m olist ingest

profile:
    uv run python -m olist profile

lint:
    uv run ruff check .

test:
    uv run pytest

check: lint test
