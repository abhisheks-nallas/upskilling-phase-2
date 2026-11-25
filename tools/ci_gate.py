"""CI quality gate (G-4): runs a small RAGAS check on RAG v2 and fails if any metric drops more than 10% below the baseline.

    backend\\.venv\\Scripts\\python.exe tools\\ci_gate.py                    # check against docs/ragas-baseline.json
    backend\\.venv\\Scripts\\python.exe tools\\ci_gate.py --update-baseline  # measure again and save as the new baseline

It uses the first 6 questions only, so one run stays inside the Groq free tier. GitHub Actions runs it on every PR
(.github/workflows/rag-gate.yml). Measure the baseline with the same judge CI uses (Groq), not the local one.
"""
import argparse
import json
import math
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "docs" / "ragas-baseline.json"
METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
MAX_DROP = 0.10   # G-4: block the PR when a metric is more than 10% below the baseline
QUESTIONS = 6


def check(scores: dict, baseline: dict, max_drop: float = MAX_DROP) -> list[tuple]:
    """Returns (metric, baseline, now, change, ok) for every metric. A missing or NaN score counts as a failure."""
    rows = []
    for m in METRICS:
        base, now = baseline[m], scores.get(m)
        if now is None or math.isnan(now):
            rows.append((m, base, float("nan"), float("nan"), False))
            continue
        change = (now - base) / base if base else 0.0
        rows.append((m, base, now, change, change >= -max_drop))
    return rows


def render(rows: list[tuple], max_drop: float = MAX_DROP) -> str:
    lines = [f"| Metric | Baseline | Now | Change | Limit -{max_drop:.0%} |", "|---|---|---|---|---|"]
    lines += [f"| {m} | {b:.3f} | {n:.3f} | {c:+.1%} | {'ok' if ok else 'FAIL'} |" for m, b, n, c, ok in rows]
    return "\n".join(lines)


def measure() -> dict:
    sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "tools")]
    import rag_eval as ev   # heavy imports, so they stay out of the tests
    from langchain_litellm import ChatLiteLLM
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from plan_graph import make_llm
    from rag import Retriever, ask

    questions = json.loads((ROOT / "backend" / "eval" / "questions.json").read_text(encoding="utf-8"))[:QUESTIONS]
    llm, retriever = make_llm(), Retriever("v2")
    rows = []
    for q in questions:
        print(f"answering '{q['question'][:60]}'", flush=True)
        rows.append({**ask(q["question"], retriever=retriever, llm=llm), "reference": q["reference"]})
    judge_model = f"groq/{os.environ.get('GROQ_JUDGE_MODEL', 'openai/gpt-oss-120b')}"
    judge = LangchainLLMWrapper(ev.PacedJudge(model=judge_model, temperature=0, max_tokens=4000))
    frame = ev.score(rows, judge, LangchainEmbeddingsWrapper(ev.LocalEmbeddings()))
    ev.get_client().flush()   # sends the traces before the process ends
    return {m: ev.mean(frame[m].tolist()) for m in METRICS} | {"judge": judge_model, "questions": len(rows)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()
    scores = measure()
    print(json.dumps(scores, indent=1))
    if args.update_baseline:
        BASELINE.write_text(json.dumps({**scores, "date": str(date.today())}, indent=1) + "\n", encoding="utf-8")
        print(f"Baseline saved to {BASELINE}")
        return
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    rows = check(scores, baseline)
    table = render(rows)
    print(table)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text("## RAGAS quality gate\n\n" + table + "\n", encoding="utf-8")
    if not all(r[-1] for r in rows):
        sys.exit("Quality gate FAILED: a metric dropped more than 10% below the baseline.")
    print("Quality gate passed.")


if __name__ == "__main__":
    main()
