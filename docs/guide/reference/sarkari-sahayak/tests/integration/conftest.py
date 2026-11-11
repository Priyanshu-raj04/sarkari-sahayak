import os
from collections.abc import Iterator

import psycopg
import pytest

from sahayak.store.migrate import migrate
from sahayak.store.repo import connect


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    """A migrated database with empty tables. Needs `make up` (or the CI service container)."""
    url = os.environ.get("TEST_DATABASE_URL", "postgresql://sahayak:sahayak@localhost:5432/sahayak")
    try:
        c = connect(url)
    except psycopg.OperationalError:
        if os.environ.get("CI"):  # never silently skip in CI
            raise
        pytest.skip("Postgres not reachable — run `make up`")
    migrate(c)
    c.execute("TRUNCATE documents CASCADE")
    c.commit()
    yield c
    c.close()
