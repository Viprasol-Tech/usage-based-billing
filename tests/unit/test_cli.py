"""CLI smoke tests."""

from __future__ import annotations

from typer.testing import CliRunner

from usage_based_billing import __version__
from usage_based_billing.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_demo_runs_and_prints_total() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "TOTAL" in result.stdout
    assert "Invoice" in result.stdout
