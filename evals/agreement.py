"""Judge-agreement statistics."""

from collections.abc import Sequence


def cohens_kappa(a: Sequence[bool], b: Sequence[bool]) -> float:
    """Cohen's kappa for two binary raters. 1 = perfect agreement, 0 = chance level."""
    if len(a) != len(b) or not a:
        msg = "need two non-empty label lists of equal length"
        raise ValueError(msg)
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1 - expected)
