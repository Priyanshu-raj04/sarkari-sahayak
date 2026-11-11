"""Shared benchmark dataset types."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BenchDataset:
    """topics: qid→query; qrels: qid→{docid→rel}; corpus: docid→text."""

    name: str
    split: str
    topics: dict[str, str]
    qrels: dict[str, dict[str, int]]
    corpus: dict[str, str]

    @property
    def n_queries(self) -> int:
        return len(self.topics)

    @property
    def corpus_size(self) -> int:
        return len(self.corpus)
