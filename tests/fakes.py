"""Hand-written fakes for our own ports (prefer these over mocks)."""

from dataclasses import dataclass, field

from pydantic import BaseModel

from sahayak.retrieve.types import Passage


@dataclass
class FakeRetriever:
    name: str
    results: dict[str, list[str]]
    calls: list[tuple[str, int]] = field(default_factory=list)
    fail: bool = False

    def search(self, query: str, k: int) -> list[str]:
        self.calls.append((query, k))
        if self.fail:
            raise RuntimeError(f"{self.name} down")
        return self.results.get(query, [])[:k]


@dataclass
class DictStore:
    passages: dict[str, Passage]

    def get_many(self, chunk_ids: list[str]) -> dict[str, Passage]:
        return {c: self.passages[c] for c in chunk_ids if c in self.passages}


@dataclass
class FakeReranker:
    scores: dict[str, float]

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [self.scores.get(t, 0.0) for t in texts]


def passage(cid: str, text: str = "", lang: str = "hi") -> Passage:
    doc_id = cid.split("#", maxsplit=1)[0]
    return Passage(chunk_id=cid, doc_id=doc_id, lang=lang, page=1, text=text or cid)


class FakeLLM:
    """Returns scripted outputs per schema type, in order; records every call."""

    def __init__(self, script: dict[type[BaseModel], list[BaseModel | Exception]]) -> None:
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[tuple[str, str, type[BaseModel]]] = []

    def complete_json[T: BaseModel](
        self, *, system: str, user: str, schema: type[T], temperature: float = 0.0
    ) -> T:
        self.calls.append((system, user, schema))
        queue = self.script.get(schema, [])
        if not queue:
            raise AssertionError(f"FakeLLM: no scripted output left for {schema.__name__}")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if not isinstance(item, schema):
            raise TypeError(f"FakeLLM: scripted {type(item).__name__}, expected {schema.__name__}")
        return item
