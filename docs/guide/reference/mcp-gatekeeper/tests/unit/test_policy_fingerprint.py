from pathlib import Path

from gatekeeper.fingerprint import Lockfile, fingerprint
from gatekeeper.models import ToolSpec
from gatekeeper.policy import ArgRule, Policy, ToolPolicy

T = ToolSpec(name="search", description="खोज", input_schema={"type": "object"})


def test_fingerprint_is_order_independent_and_unicode_safe() -> None:
    a = ToolSpec(name="x", input_schema={"a": 1, "b": 2})
    b = ToolSpec(name="x", input_schema={"b": 2, "a": 1})
    assert fingerprint(a) == fingerprint(b)
    assert fingerprint(T) != fingerprint(T.model_copy(update={"description": "खोज "}))


def test_lockfile_roundtrip(tmp_path: Path) -> None:
    lock = Lockfile.from_tools("s", [T])
    lock.save(tmp_path / "l.json")
    assert Lockfile.load(tmp_path / "l.json") == lock
    assert lock.check(T) == "ok"
    assert lock.check(ToolSpec(name="new")) == "unpinned"


def test_policy_rules(tmp_path: Path) -> None:
    (tmp_path / "p.yaml").write_text(
        "default_max_string: 5\n"
        "tools:\n"
        "  search:\n"
        "    args:\n"
        "      lang: {allowed: [hi, en]}\n"
        "      query: {pattern: '[\\p{L} ]+'}\n",
        encoding="utf-8",
    )
    policy = Policy.load(tmp_path / "p.yaml")
    assert policy.violations("search", {"lang": "hi", "query": "KYC"}) == []
    assert policy.violations("search", {"lang": "fr"}) == [
        "argument 'lang' has a value outside the allow-list"
    ]
    assert "does not match" in policy.violations("search", {"query": "a;b"})[0]
    assert "not allowed" in policy.violations("search", {"extra": 1})[0]
    assert "longer than 5" in policy.violations("unknown_tool", {"q": "123456"})[0]


def test_empty_policy_file(tmp_path: Path) -> None:
    (tmp_path / "p.yaml").write_text("", encoding="utf-8")
    assert Policy.load(tmp_path / "p.yaml") == Policy()
    assert ToolPolicy().args == {}
    assert ArgRule().pattern is None
