import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from latency_alert import check, percentile


def test_percentile_nearest_rank():
    values = list(range(1, 21))   # 1..20
    assert percentile(values, 50) == 10
    assert percentile(values, 95) == 19


def test_within_limit_passes():
    assert check([1.0, 2.0, 3.0], limit=5)[2]


def test_over_limit_alerts():
    p50, p95, ok = check([1.0] * 18 + [9.0, 9.5], limit=5)
    assert (p50, p95, ok) == (1.0, 9.0, False)


def test_no_traces_does_not_alert():
    assert check([], limit=1)[2]
