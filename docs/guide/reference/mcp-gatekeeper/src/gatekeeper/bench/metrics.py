"""Binary-classification metrics for detector benchmarks."""

from collections.abc import Sequence

from pydantic import BaseModel


class Scores(BaseModel):
    n: int
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float
    recall: float
    f1: float
    fpr: float


def binary_scores(y_true: Sequence[bool], y_pred: Sequence[bool]) -> Scores:
    """Positive class = poisoned. Undefined ratios (0/0) are reported as 0.0."""
    if len(y_true) != len(y_pred):
        msg = "y_true and y_pred differ in length"
        raise ValueError(msg)
    tp = sum(t and p for t, p in zip(y_true, y_pred, strict=True))
    fp = sum((not t) and p for t, p in zip(y_true, y_pred, strict=True))
    fn = sum(t and (not p) for t, p in zip(y_true, y_pred, strict=True))
    tn = len(y_true) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return Scores(
        n=len(y_true),
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        fpr=round(fpr, 4),
    )
