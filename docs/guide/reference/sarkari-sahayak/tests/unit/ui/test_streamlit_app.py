"""SE-17 / SE-19: UI behaviour with the API mocked (respx)."""

from pathlib import Path

import httpx
import pytest
import respx
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[3] / "app" / "streamlit_app.py")
ANSWER = {
    "run_id": "r1",
    "answer": "दस साल [MD-KYC#p1c0]",
    "citations": [{"chunk_id": "MD-KYC#p1c0", "text": "केवाईसी...", "source_url": ""}],
    "refused": False,
    "degraded": False,
    "latency_ms": 5,
}


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setenv("SAHAYAK_API_URL", "http://api.test")
    return AppTest.from_file(APP, default_timeout=10).run()


@respx.mock
def test_shows_answer_and_citation_expander(app: AppTest) -> None:
    respx.post("http://api.test/v1/ask").mock(return_value=httpx.Response(200, json=ANSWER))
    app.text_input(key="question").input("केवाईसी?").run()
    app.button[0].click().run()
    assert not app.exception
    assert any("दस साल" in m.value for m in app.markdown)
    assert app.expander[0].label == "📄 MD-KYC#p1c0"


@respx.mock
def test_cold_start_timeout_shows_wake_up_message(app: AppTest) -> None:
    respx.post("http://api.test/v1/ask").mock(side_effect=httpx.ReadTimeout("slow"))
    app.text_input(key="question").input("केवाईसी?").run()
    app.button[0].click().run()
    assert "waking up" in app.warning[0].value


@respx.mock
def test_rate_limit_message(app: AppTest) -> None:
    respx.post("http://api.test/v1/ask").mock(
        return_value=httpx.Response(429, headers={"retry-after": "30"}, json={})
    )
    app.text_input(key="question").input("केवाईसी?").run()
    app.button[0].click().run()
    assert "30" in app.warning[0].value
