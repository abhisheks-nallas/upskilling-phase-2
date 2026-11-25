import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from ci_gate import METRICS, check

BASE = {m: 0.8 for m in METRICS}


def test_same_scores_pass():
    assert all(r[-1] for r in check(dict(BASE), BASE))


def test_small_drop_passes_and_big_drop_fails():
    assert all(r[-1] for r in check({**BASE, "faithfulness": 0.74}, BASE))   # -7.5%
    failed = [r[0] for r in check({**BASE, "faithfulness": 0.70}, BASE) if not r[-1]]   # -12.5%
    assert failed == ["faithfulness"]


def test_improvement_passes():
    assert all(r[-1] for r in check({m: 0.95 for m in METRICS}, BASE))


def test_missing_or_nan_score_fails():
    nan = float("nan")
    assert not all(r[-1] for r in check({**BASE, "context_recall": nan}, BASE))
    assert not all(r[-1] for r in check({m: v for m, v in BASE.items() if m != "context_recall"}, BASE))
