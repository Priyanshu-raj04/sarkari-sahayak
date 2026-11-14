from typer.testing import CliRunner

from sahayak import __version__
from sahayak.cli import app


def test_version_command_prints_package_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_help_lists_db_and_ingest() -> None:
    out = CliRunner().invoke(app, ["--help"]).stdout
    for cmd in ("db", "ingest", "version", "serve"):
        assert cmd in out


def test_db_help_lists_migrate() -> None:
    out = CliRunner().invoke(app, ["db", "--help"]).stdout
    assert "migrate" in out
