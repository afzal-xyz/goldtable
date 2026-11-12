"""Smoke tests for the CLI scaffold."""

from typer.testing import CliRunner

from goldtable import __version__
from goldtable.cli import app

runner = CliRunner()


def test_help_lists_diff() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "diff" in result.output


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_diff_stub_exits_2() -> None:
    result = runner.invoke(app, ["diff", "a.parquet", "b.csv"])
    assert result.exit_code == 2
