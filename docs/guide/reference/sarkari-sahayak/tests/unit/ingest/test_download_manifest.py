from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from pydantic import HttpUrl

from sahayak.ingest.download import DisallowedError, PoliteDownloader
from sahayak.ingest.manifest import ManifestRow, read_manifest, sha256_file, write_manifest


class Clock:
    def __init__(self) -> None:
        self.t = 0.0
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s


@respx.mock
def test_downloads_respecting_robots_rate_limit_and_cache(tmp_path: Path) -> None:
    respx.get("https://rbi.test/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
    )
    pdf = respx.get("https://rbi.test/docs/md.pdf").mock(
        return_value=httpx.Response(200, content=b"%PDF-1.7")
    )
    clock = Clock()
    dl = PoliteDownloader(tmp_path, client=httpx.Client(), sleep=clock.sleep, clock=clock.now)
    path = dl.fetch("https://rbi.test/docs/md.pdf")
    assert path.read_bytes() == b"%PDF-1.7"
    assert path.suffix == ".pdf"
    assert clock.slept == [3.0]  # robots.txt request, then waited before the PDF
    assert dl.fetch("https://rbi.test/docs/md.pdf") == path  # cached: no new request
    assert pdf.call_count == 1
    with pytest.raises(DisallowedError):
        dl.fetch("https://rbi.test/private/x.pdf")


@respx.mock
def test_missing_robots_allows_and_http_errors_raise(tmp_path: Path) -> None:
    respx.get("https://x.test/robots.txt").mock(return_value=httpx.Response(404))
    respx.get("https://x.test/a").mock(return_value=httpx.Response(500))
    dl = PoliteDownloader(tmp_path, client=httpx.Client(), min_interval_s=0)
    with pytest.raises(httpx.HTTPStatusError):
        dl.fetch("https://x.test/a")


def test_manifest_roundtrip_and_hash(tmp_path: Path) -> None:
    rows = [
        ManifestRow(
            doc_id="MD-KYC-2016-EN",
            title="Master Direction - KYC",
            lang="en",
            doc_type="master_direction",
            url=HttpUrl("https://rbi.test/md.pdf"),
            issued_on=date(2016, 2, 25),
            pair_doc_id="MD-KYC-2016-HI",
        ),
    ]
    path = tmp_path / "m.csv"
    write_manifest(path, rows)
    assert read_manifest(path) == rows
    (tmp_path / "f").write_bytes(b"abc")
    assert sha256_file(tmp_path / "f").startswith("ba7816bf")
