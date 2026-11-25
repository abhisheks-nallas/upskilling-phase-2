"""p95 latency alert (G-4): reads recent `rag-query` traces from Langfuse and fails when p95 latency is over the limit.

    backend\\.venv\\Scripts\\python.exe tools\\latency_alert.py                       # last 24 h, limit 8 s
    backend\\.venv\\Scripts\\python.exe tools\\latency_alert.py --limit 0.5 --hours 72  # a low limit, to see the alert fire

Langfuse Hobby has no alerting, so this runs as a scheduled GitHub Action (.github/workflows/latency-alert.yml).
A failed run is the alert: GitHub emails the repo owner.
"""
import argparse
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile, e.g. p=95 of 20 values is the 19th smallest."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def check(latencies: list[float], limit: float) -> tuple[float, float, bool]:
    """Returns p50, p95 and whether p95 is within the limit. No traces at all is fine: nothing to alert on."""
    if not latencies:
        return 0.0, 0.0, True
    p95 = percentile(latencies, 95)
    return percentile(latencies, 50), p95, p95 <= limit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=float, default=8.0, help="p95 limit in seconds")
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()

    import httpx
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")
    since = (datetime.now(timezone.utc) - timedelta(hours=args.hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # the old /traces endpoint was removed from Langfuse Cloud in Nov 2026, so we read the root "rag-query" spans from the v2 observations API
    r = httpx.get(os.environ.get("LANGFUSE_BASE_URL", os.environ.get("LANGFUSE_HOST", "")).rstrip("/") + "/api/public/v2/observations",
                  params={"fields": "core,basic", "fromStartTime": since, "limit": 1000, "type": "SPAN"},   # shortcut: one page of 1000, enough for this app
                  auth=(os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"]), timeout=30)
    r.raise_for_status()
    latencies = [o["latency"] for o in r.json()["data"] if o["name"] == "rag-query" and o.get("latency") is not None]
    p50, p95, ok = check(latencies, args.limit)
    print(f"{len(latencies)} rag-query traces in the last {args.hours} h: p50 {p50:.2f}s, p95 {p95:.2f}s, limit {args.limit}s")
    if not ok:
        sys.exit(f"ALERT: p95 latency {p95:.2f}s is over the {args.limit}s limit.")
    print("p95 latency is within the limit.")


if __name__ == "__main__":
    main()
