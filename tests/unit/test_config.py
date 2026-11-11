import pytest

from sahayak.config import Profile, Settings


def test_defaults_are_local_profile() -> None:
    s = Settings()
    assert s.profile is Profile.LOCAL
    assert s.top_k == 8


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAHAYAK_PROFILE", "hosted")
    monkeypatch.setenv("SAHAYAK_TOP_K", "5")
    monkeypatch.setenv("SAHAYAK_GROQ_API_KEY", "gsk_test")
    s = Settings()
    assert s.profile is Profile.HOSTED
    assert s.top_k == 5
    assert s.groq_api_key is not None
    assert s.groq_api_key.get_secret_value() == "gsk_test"
    assert "gsk_test" not in repr(s)  # secrets never leak into logs


def test_rejects_invalid_top_k(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAHAYAK_TOP_K", "0")
    with pytest.raises(ValueError, match="top_k"):
        Settings()
