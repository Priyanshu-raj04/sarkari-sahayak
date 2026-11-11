from typer.testing import CliRunner

from sahayak import __version__
from sahayak.cli import app


def test_version_command_prints_package_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_help_lists_all_commands() -> None:
    out = CliRunner().invoke(app, ["--help"]).stdout
    for cmd in ("db", "golden", "ingest", "serve", "version"):
        assert cmd in out
