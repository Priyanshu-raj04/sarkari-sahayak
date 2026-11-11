"""`sahayak` command-line entry point. Heavy imports stay inside commands (fast `--help`)."""

from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import typer

from sahayak import __version__

app = typer.Typer(no_args_is_help=True, help="Sarkari Sahayak CLI")
db_app = typer.Typer(no_args_is_help=True, help="Database commands")
golden_app = typer.Typer(no_args_is_help=True, help="Flight Recorder golden set")
app.add_typer(db_app, name="db")
app.add_typer(golden_app, name="golden")

GOLDEN = Path("evals/golden/golden.jsonl")


@app.callback()
def main() -> None:
    """Sarkari Sahayak: ingest, index, benchmark and serve."""


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@db_app.command("migrate")
def db_migrate() -> None:
    """Apply pending SQL migrations."""
    from sahayak.config import get_settings  # noqa: PLC0415
    from sahayak.store.migrate import migrate  # noqa: PLC0415
    from sahayak.store.repo import connect  # noqa: PLC0415

    applied = migrate(connect(get_settings().database_url))
    typer.echo(f"applied: {', '.join(applied) or 'nothing (up to date)'}")


@app.command()
def ingest(
    manifest: Annotated[Path, typer.Option(exists=True)] = Path("data_manifest/rbi_manifest.csv"),
    cache: Annotated[Path, typer.Option()] = Path("data/raw"),
    only: Annotated[str | None, typer.Option(help="ingest a single doc_id")] = None,
) -> None:
    """Download, extract, chunk, embed and store every document in the manifest."""
    from sahayak.config import get_settings  # noqa: PLC0415
    from sahayak.embed.e5 import E5Embedder  # noqa: PLC0415
    from sahayak.ingest.download import PoliteDownloader  # noqa: PLC0415
    from sahayak.ingest.manifest import read_manifest  # noqa: PLC0415
    from sahayak.ingest.pdf import extract_pages  # noqa: PLC0415
    from sahayak.ingest.pipeline import IngestPipeline  # noqa: PLC0415
    from sahayak.store.repo import PgRepository, connect  # noqa: PLC0415

    settings = get_settings()
    pipeline = IngestPipeline(
        fetcher=PoliteDownloader(cache),
        extract=lambda p, hi: extract_pages(p, expect_hindi=hi),
        embedder=E5Embedder.load(settings.embed_model),
        writer=PgRepository(connect(settings.database_url)),
    )
    for row in read_manifest(manifest):
        if only and row.doc_id != only:
            continue
        report = pipeline.ingest(row)
        flag = "  ⚠️ script mismatch" if report.script_mismatch else ""
        typer.echo(
            f"{row.doc_id}: {report.pages} pages ({report.ocr_pages} OCR), "
            f"{report.chunks} chunks{flag}"
        )


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the REST + MCP server."""
    import uvicorn  # noqa: PLC0415

    from sahayak.api.app import build_app  # noqa: PLC0415
    from sahayak.bootstrap import build_service  # noqa: PLC0415
    from sahayak.config import Profile, get_settings  # noqa: PLC0415
    from sahayak.logging import configure_logging  # noqa: PLC0415

    settings = get_settings()
    configure_logging(settings.log_level, json=settings.log_json)
    app_ = build_app(
        build_service(settings),
        per_minute=settings.rate_limit_per_minute,
        trust_proxy=settings.profile is Profile.HOSTED,  # Render sets X-Forwarded-For
    )
    uvicorn.run(app_, host=host, port=port)


@golden_app.command("add")
def golden_add(
    run_id: str,
    expect: Annotated[str, typer.Option(help="answer | refuse")],
    failure_mode: Annotated[str, typer.Option()],
    must_cite: Annotated[
        list[str] | None, typer.Option(help="doc_id(s) that must be cited")
    ] = None,
    path: Path = GOLDEN,
) -> None:
    """Promote a flagged run into the golden regression set."""
    from sahayak.config import get_settings  # noqa: PLC0415
    from sahayak.flight.golden import GoldenCase, append_case, load_cases, next_id  # noqa: PLC0415
    from sahayak.flight.runs import RunStore  # noqa: PLC0415
    from sahayak.store.repo import connect  # noqa: PLC0415
    from sahayak.text.normalize import detect_script  # noqa: PLC0415

    run = RunStore(connect(get_settings().database_url)).get(run_id)
    if run is None:
        raise typer.BadParameter(f"unknown run_id {run_id}")
    script = detect_script(run["question"])
    lang: Literal["hi", "en", "hinglish"] = (
        "hi" if script == "hi" else "en" if script == "en" else "hinglish"
    )
    if expect not in ("answer", "refuse"):
        raise typer.BadParameter("expect must be 'answer' or 'refuse'")
    path.parent.mkdir(parents=True, exist_ok=True)
    case = GoldenCase(
        id=next_id(load_cases(path)),
        question=run["question"],
        lang=lang,
        expect=expect,  # type: ignore[arg-type]
        must_cite_doc_ids=must_cite or [],
        source_run_id=run_id,
        failure_mode=failure_mode,
        added_on=date.today(),
    )
    append_case(path, case)
    typer.echo(f"added {case.id} from run {run_id}")
