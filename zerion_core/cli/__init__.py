"""Zerion-Core terminal UI."""

__all__ = ["run_cli"]


def run_cli() -> None:
    from zerion_core.cli.app import run_cli as _run_cli

    _run_cli()
