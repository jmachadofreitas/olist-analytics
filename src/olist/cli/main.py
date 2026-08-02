"""Olist command-line interface."""

import typer

from olist.ingestion import load_raw_data
from olist.profiling import profile_raw_sources

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def ingest() -> None:
    """Load the raw CSV files into DuckDB."""

    for result in load_raw_data():
        typer.echo(f"raw.{result.table}: {result.rows:,} rows")


@app.command()
def profile() -> None:
    """Profile the raw tables in DuckDB."""

    result = profile_raw_sources()
    typer.echo(f"Profile run: {result.run_id}")
    typer.echo(f"Tables: {result.table_count}")
    typer.echo(f"Failed checks: {result.failed_check_count}")
    typer.echo(f"Report: {result.report_path}")


def main() -> None:
    app()
