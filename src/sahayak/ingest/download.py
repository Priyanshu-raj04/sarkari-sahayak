"""Polite HTTP cache for corpus files.

Honours robots.txt, sends a clear User-Agent, rate-limits requests, and caches by URL hash.
When RBI's WAF returns a captcha HTML page, raises DisallowedError so callers can drop a
manual Print→PDF into data/raw/ instead of ingesting garbage.
"""

import hashlib
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import structlog

log = structlog.get_logger()
USER_AGENT = "sarkari-sahayak-research/0.1 (+https://github.com/Priyanshu-raj04/sarkari-sahayak)"


class DisallowedError(RuntimeError):
    """robots.txt forbids this URL, or the response was a bot-protection interstitial."""


class PoliteDownloader:
    """Fetch-or-cache one URL under cache_dir/<sha256(url)[:24]>.{pdf|html}."""

    def __init__(
        self,
        cache_dir: Path,
        client: httpx.Client | None = None,
        min_interval_s: float = 3.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cache_dir = cache_dir
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True
        )
        self.min_interval_s, self.sleep, self.clock = min_interval_s, sleep, clock
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request: float | None = None

    def fetch(self, url: str) -> Path:
        """Return a local path for url, using cache when present (incl. manual .pdf drops)."""
        target = self.cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:24] + _suffix(url))
        hit = _resolve_cache_hit(target)
        if hit is not None:
            return hit
        if not self._allowed(url):
            raise DisallowedError(url)
        self._wait()
        resp = self.client.get(url)
        resp.raise_for_status()
        content = resp.content
        if _looks_like_waf_interstitial(content):
            raise DisallowedError(
                f"download blocked by bot protection (captcha/WAF) for {url}; "
                "save the PDF manually into the cache path and re-run"
            )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        log.info("downloaded", url=url, bytes=len(content))
        return target

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._robots:
            parser = RobotFileParser()
            self._wait()
            resp = self.client.get(f"{root}/robots.txt")
            parser.parse(resp.text.splitlines() if resp.status_code == 200 else [])
            self._robots[root] = parser
        return self._robots[root].can_fetch(USER_AGENT, url)

    def _wait(self) -> None:
        now = self.clock()
        if self._last_request is not None:
            remaining = self.min_interval_s - (now - self._last_request)
            if remaining > 0:
                self.sleep(remaining)
        self._last_request = self.clock()


def _suffix(url: str) -> str:
    path = urlsplit(url).path.lower()
    return ".pdf" if path.endswith(".pdf") else ".html"


def _resolve_cache_hit(target: Path) -> Path | None:
    """Prefer an existing cache file; for non-pdf URLs also accept a manual *.pdf sibling."""
    if target.exists():
        return target
    if target.suffix != ".pdf":
        sibling = target.with_suffix(".pdf")
        if sibling.exists():
            return sibling
    return None


def _looks_like_waf_interstitial(content: bytes) -> bool:
    """rbidocs sometimes returns an HTML captcha page instead of the PDF."""
    head = content[:2048].lstrip().lower()
    if head.startswith(b"%pdf"):
        return False
    markers = (b"please enable javascript", b"support id", b"akamai", b"<html")
    return any(m in head for m in markers)
