"""Slow smoke: real CrossEncoder (skipped unless --runslow / RUN_SLOW=1 and ml extra)."""

import os

import pytest

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("RUN_SLOW") != "1",
        reason="set RUN_SLOW=1 to download/run CrossEncoder (~2GB)",
    ),
]


def test_cross_encoder_ranks_relevant_pair_higher() -> None:
    from sahayak.retrieve.rerank import CrossEncoderReranker  # noqa: PLC0415

    rr = CrossEncoderReranker()
    query = "केवाईसी नियम क्या हैं?"
    texts = [
        "मौसम आज बहुत अच्छा है और पार्क में बच्चे खेल रहे हैं।",
        "बैंकों को केवाईसी दिशानिर्देशों का पालन करना अनिवार्य है।",
        "क्रिकेट मैच का स्कोर तीन विकेट पर 250 रन है।",
    ]
    scores = rr.score(query, texts)
    assert scores[1] == max(scores)
