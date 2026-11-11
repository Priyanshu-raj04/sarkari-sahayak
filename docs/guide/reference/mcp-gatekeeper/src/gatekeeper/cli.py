"""`gatekeeper` CLI: scan tool definitions, pin them, emit SARIF."""

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from gatekeeper import __version__
from gatekeeper.detectors.heuristic import scan_tool
from gatekeeper.fingerprint import Lockfile
from gatekeeper.models import Finding, ToolSpec
from gatekeeper.sarif import to_sarif

app = typer.Typer(no_args_is_help=True, help="MCP Gatekeeper — a firewall for MCP tools")
_RANK = {"low": 1, "medium": 2, "high": 3}


class Fmt(StrEnum):
    TEXT = "text"
    JSON = "json"
    SARIF = "sarif"


class FailOn(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def load_tools(path: Path) -> list[ToolSpec]:
    """Load a saved `tools/list` result: {"tools": [...]} or a bare list."""
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["tools"] if isinstance(data, dict) else data
    return [
        ToolSpec(
            name=t["name"],
            description=t.get("description") or "",
            input_schema=t.get("inputSchema", t.get("input_schema", {})),
        )
        for t in items
    ]


@app.callback()
def main() -> None:
    """Scan, pin and protect MCP tools."""


@app.command()
def version() -> None:
    typer.echo(__version__)


@app.command()
def scan(
    tools: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="tools/list JSON")],
    fmt: Annotated[Fmt, typer.Option("--format")] = Fmt.TEXT,
    output: Annotated[Path | None, typer.Option(help="write report here")] = None,
    fail_on: Annotated[FailOn, typer.Option()] = FailOn.HIGH,
) -> None:
    """Scan tool definitions for poisoning. Exit code 1 if a finding ≥ --fail-on exists."""
    findings: list[Finding] = [f for t in load_tools(tools) for f in scan_tool(t)]
    if fmt is Fmt.SARIF:
        report = json.dumps(to_sarif(findings, tools.as_posix()), indent=2, ensure_ascii=False)
    elif fmt is Fmt.JSON:
        report = json.dumps([f.model_dump() for f in findings], indent=2, ensure_ascii=False)
    else:
        report = "\n".join(f"[{f.severity}] {f.tool}: {f.rule_id} {f.message}" for f in findings)
        report = report or "no findings"
    if output:
        output.write_text(report + "\n", encoding="utf-8")
    else:
        typer.echo(report)
    if fail_on is not FailOn.NONE and any(_RANK[f.severity] >= _RANK[fail_on] for f in findings):
        raise typer.Exit(code=1)


@app.command()
def pin(
    tools: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    server: Annotated[str, typer.Option()],
    lockfile: Annotated[Path, typer.Option()] = Path("gatekeeper.lock.json"),
) -> None:
    """Record fingerprints of the current tool definitions (commit the lockfile)."""
    lock = Lockfile.from_tools(server, load_tools(tools))
    lock.save(lockfile)
    typer.echo(f"pinned {len(lock.tools)} tools → {lockfile}")


@app.command()
def verify(
    tools: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    lockfile: Annotated[Path, typer.Option(exists=True)] = Path("gatekeeper.lock.json"),
) -> None:
    """Fail if any tool drifted from, or is missing in, the lockfile (rug-pull check)."""
    lock = Lockfile.load(lockfile)
    bad = [(t.name, s) for t in load_tools(tools) if (s := lock.check(t)) != "ok"]
    for name, status in bad:
        typer.echo(f"{status}: {name}")
    if bad:
        raise typer.Exit(code=1)
    typer.echo("all tools match the lockfile")
