"""`sahayak` CLI entry point (`version`, `db migrate`, `ingest`).

Heavy imports stay inside command bodies so `--help` stays fast. `ingest` uses
`E5Embedder` (`uv sync --extra ml`).
"""

from pathlib import Path
from typing import Annotated

import typer

from sahayak import __version__

app = typer.Typer(no_args_is_help=True, help="Sarkari Sahayak CLI")
db_app = typer.Typer(no_args_is_help=True, help="Database commands")
app.add_typer(db_app, name="db")


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
    import platform  # noqa: PLC0415

    from sahayak.config import get_settings  # noqa: PLC0415
    from sahayak.embed.e5 import E5Embedder  # noqa: PLC0415
    from sahayak.ingest.download import PoliteDownloader  # noqa: PLC0415
    from sahayak.ingest.manifest import read_manifest  # noqa: PLC0415
    from sahayak.ingest.pdf import extract_pages  # noqa: PLC0415
    from sahayak.ingest.pipeline import IngestPipeline  # noqa: PLC0415
    from sahayak.store.repo import PgRepository, connect  # noqa: PLC0415

    settings = get_settings()
    device: str | None = None
    if platform.system() == "Darwin":
        try:
            import torch  # type: ignore[import-not-found]  # noqa: PLC0415

            if torch.backends.mps.is_available():
                device = "mps"
        except ImportError:
            device = None
    pipeline = IngestPipeline(
        fetcher=PoliteDownloader(cache),
        extract=lambda p, hi: extract_pages(p, expect_hindi=hi),
        embedder=E5Embedder.load(settings.embed_model, device=device),
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
