import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from sahayak.config import get_settings


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every test starts with no SAHAYAK_* env vars and no .env file in cwd."""
    for key in list(os.environ):
        if key.startswith("SAHAYAK_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
