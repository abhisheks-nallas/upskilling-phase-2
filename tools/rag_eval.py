
"""Runs the eval questions through RAG v1 and v2, scores every answer with RAGAS, sends the scores to Langfuse
and writes docs/ragas-report.md (before vs after table) and docs/ragas-results.csv (every query).

    backend\\.venv\\Scripts\\python.exe tools\\rag_eval.py                 # full run, both versions
    backend\\.venv\\Scripts\\python.exe tools\\rag_eval.py --limit 3       # quick check with 3 questions
    backend\\.venv\\Scripts\\python.exe tools\\rag_eval.py --fresh         # forget saved answers and scores, start over

Progress is saved in tools/.rag_eval_cache.json after every step. The Groq free tier has a daily token limit,
so if it runs out, just run the same command again later and it carries on where it stopped.
Use --fresh after changing the documents, the questions or the RAG code.
"""
import argparse
import asyncio
import csv
import json
import math
import os
import sys
import time
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # model answers can contain characters the Windows console can't print
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # avoids noisy "event loop is closed" errors at exit
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env")
os.environ["LANGSMITH_TRACING"] = "false"  # eval runs go to Langfuse only, not into the LangSmith agent project

from langchain_core.embeddings import Embeddings
from langchain_litellm import ChatLiteLLM
from langfuse import get_client
from ragas import EvaluationDataset, RunConfig, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

from plan_graph import make_llm
from rag import Retriever, ask, default_embedder

METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
TARGET = 0.15      # G-3: at least 15% better than the baseline, on at least 3 of the 4 metrics
BATCH = 2          # questions scored per RAGAS call, so progress is saved often
JUDGE_PAUSE = 12   # seconds between judge calls, see PacedJudge
CACHE = ROOT / "tools" / ".rag_eval_cache.json"


class LocalEmbeddings(Embeddings):
    """Lets RAGAS reuse the same small local model as the retriever."""
    def __init__(self):
        self.fn = default_embedder()

    def embed_documents(self, texts):
        return [[float(x) for x in v] for v in self.fn(texts)]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


class PacedJudge(ChatLiteLLM):
    """The Groq free tier allows 8,000 tokens a minute and one judge call is about 1,500, so we wait between calls."""
    async def _agenerate(self, *args, **kwargs):
        result = await super()._agenerate(*args, **kwargs)
        await asyncio.sleep(JUDGE_PAUSE)
        return result


def load_cache():
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def save_cache(cache):
    CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")


def ask_with_retry(question, retriever, llm):
    for attempt in range(4):
        try:
            return ask(question, retriever=retriever, llm=llm)
        except Exception as e:  # mostly Groq rate limits on the free tier
            if attempt == 3:
                raise
            print(f"  retry in 20s ({str(e)[:80]})", flush=True)
            time.sleep(20)


def score(rows, judge, embeddings):
    answer_relevancy.strictness = 1  # RAGAS asks for 3 answers at once by default, Groq only gives one
    data = EvaluationDataset.from_list([
        {"user_input": r["question"], "response": r["answer"], "retrieved_contexts": r["contexts"], "reference": r["reference"]}
        for r in rows
    ])
    # one worker, because parallel calls trip the per-minute limit. Rate limit retries happen inside PacedJudge's LiteLLM calls
    result = evaluate(data, metrics=[faithfulness, answer_relevancy, context_precision, context_recall], llm=judge,
                      embeddings=embeddings, run_config=RunConfig(max_workers=1, timeout=300, max_retries=2), show_progress=False)
    return result.to_pandas()


def mean(values):
    values = [v for v in values if v is not None and not math.isnan(v)]
    return sum(values) / len(values) if values else float("nan")


def summarise(results):
    """Returns the table rows and how many metrics reached the +15% target."""
    table, passed = [], 0
    for m in METRICS:
        v1, v2 = (mean([r[m] for r in results[v]]) for v in ("v1", "v2"))
        change = (v2 - v1) / v1 if v1 else float("nan")
        passed += change >= TARGET
        table.append((m, v1, v2, change))
    return table, passed


def write_report(results, n, judge_model, answer_model, sample_url):
    table, passed = summarise(results)
    lines = ["| Metric | v1 baseline | v2 optimised | Change | Meets +15%? |", "|---|---|---|---|---|"]
    lines += [f"| {m} | {v1:.3f} | {v2:.3f} | {change:+.1%} | {'yes' if change >= TARGET else 'no'} |" for m, v1, v2, change in table]
    report = f"""# RAG quality: v1 baseline vs v2 optimised (G-3)

Run on {date.today():%Y-%m-%d} over {n} questions from `backend/eval/questions.json`.
Answers by `{answer_model}`, judged by `{judge_model}` (RAGAS). Retrieval is local (Chroma + MiniLM), top 3 passages.

## Result: {'PASS' if passed >= 3 else 'NOT YET'} ({passed} of 4 metrics improved by at least 15%)

{chr(10).join(lines)}

## What changed from v1 to v2

- Chunking: v1 cuts every 400 characters. v2 keeps one chunk per document section, with the document title and heading in front.
- Search: v1 uses vector search only. v2 merges vector search and keyword (BM25) search with reciprocal rank fusion.
- Prompt: v2 tells the model to answer only from the context, quote exact numbers and say when it doesn't know.

## Notes

- The change is relative to v1: (v2 - v1) / v1. A v1 score that is already high leaves little room to improve.
- Judge and answer models are both small Groq models, so scores are indicative, not absolute. The same judge scored both versions.
- Per-query scores are in `docs/ragas-results.csv` and in Langfuse (score names are the metric names, traces are tagged `rag-v1` / `rag-v2`).
- Example trace: {sample_url or 'n/a'}
"""
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "ragas-report.md").write_text(report, encoding="utf-8")
    print(report)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="only use the first N questions")
    parser.add_argument("--versions", nargs="+", default=["v1", "v2"])
    parser.add_argument("--fresh", action="store_true", help="ignore saved progress")
    parser.add_argument("--report-only", action="store_true", help="don't call any model, write the report from what is already scored")
    args = parser.parse_args()

    questions = json.loads((ROOT / "backend" / "eval" / "questions.json").read_text(encoding="utf-8"))
    if args.limit:
        questions = questions[:args.limit]
    cache = {} if args.fresh else load_cache()
    llm = make_llm()
    judge_model = f"groq/{os.environ.get('GROQ_JUDGE_MODEL', 'openai/gpt-oss-120b')}"
    judge = LangchainLLMWrapper(PacedJudge(model=judge_model, temperature=0, max_tokens=4000))
    embeddings = LangchainEmbeddingsWrapper(LocalEmbeddings())
    langfuse = get_client()
    retrievers = {v: Retriever(v) for v in args.versions}
    for v in args.versions:
        cache.setdefault(v, {})

    # a few questions at a time, both versions each time, so an interrupted run still has a fair v1 vs v2 pair
    for i in range(0, 0 if args.report_only else len(questions), BATCH):
        for version in args.versions:
            done = cache[version]
            for q in questions[i:i + BATCH]:  # 1. answer
                if q["question"] not in done:
                    print(f"{version}: answering '{q['question'][:60]}'", flush=True)
                    done[q["question"]] = {**ask_with_retry(q["question"], retrievers[version], llm), "reference": q["reference"]}
                    save_cache(cache)
                    time.sleep(2)
            batch = [done[q["question"]] for q in questions[i:i + BATCH] if any(done[q["question"]].get(m) is None for m in METRICS)]
            if not batch:
                continue
            print(f"{version}: scoring questions {i + 1}-{i + len(batch)} of {len(questions)} with RAGAS", flush=True)  # 2. score
            frame = score(batch, judge, embeddings)
            for row, (_, scores) in zip(batch, frame.iterrows()):
                for m in METRICS:
                    value = scores.get(m)
                    row[m] = None if value is None or math.isnan(value) else float(value)
                    if row[m] is not None and row["trace_id"]:
                        langfuse.create_score(trace_id=row["trace_id"], name=m, value=row[m], data_type="NUMERIC")
            save_cache(cache)
            langfuse.flush()
            if all(row[m] is None for row in batch for m in METRICS):
                sys.exit("Every score in this batch failed, most likely the Groq daily token limit. Progress is saved, run the same command again later.")

    # only questions that were fully scored in every version count, so the comparison stays fair
    scored = [q for q in questions if all(q["question"] in cache[v] and all(cache[v][q["question"]].get(m) is not None for m in METRICS) for v in args.versions)]
    if not scored:
        sys.exit("No question is fully scored yet. Run again.")
    results = {v: [cache[v][q["question"]] for q in scored] for v in args.versions}
    if len(scored) < len(questions):
        print(f"Note: {len(scored)} of {len(questions)} questions are fully scored so far. Run again to continue.")
    questions = scored

    with open(ROOT / "docs" / "ragas-results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["version", "question", "answer", "sources", *METRICS, "trace_id"])
        for version, rows in results.items():
            for r in rows:
                writer.writerow([version, r["question"], r["answer"].replace("\n", " "), ";".join(r["sources"]), *[r[m] for m in METRICS], r["trace_id"]])

    if "v1" in results and "v2" in results:
        trace_id = results["v2"][0]["trace_id"]
        write_report(results, len(questions), judge_model, llm.model, langfuse.get_trace_url(trace_id=trace_id) if trace_id else None)


if __name__ == "__main__":
    main()
