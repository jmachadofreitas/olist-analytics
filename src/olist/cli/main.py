"""Olist command-line interface."""

import typer

from olist.ingestion import load_raw_data

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def ingest() -> None:
    """Load the raw CSV files into DuckDB."""

    for result in load_raw_data():
        typer.echo(f"raw.{result.table}: {result.rows:,} rows")



def main() -> None:
    app()
