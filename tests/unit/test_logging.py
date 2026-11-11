import json

import pytest
import structlog

from sahayak.logging import configure_logging


def test_json_logs_keep_devanagari_and_context(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", json=True)
    structlog.contextvars.bind_contextvars(request_id="r-1")
    structlog.get_logger().info("query_received", q="केवाईसी नियम")
    structlog.contextvars.clear_contextvars()
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["q"] == "केवाईसी नियम"
    assert line["request_id"] == "r-1"
    assert line["level"] == "info"


def test_debug_is_filtered_at_info(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", json=True)
    structlog.get_logger().debug("noisy")
    assert "noisy" not in capsys.readouterr().out
