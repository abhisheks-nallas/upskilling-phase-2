# RAG quality: v1 baseline vs v2 optimised (G-3)

Run on 2026-11-24 over 20 questions from `backend/eval/questions.json`.
Answers by `groq/openai/gpt-oss-20b`, judged by `groq/openai/gpt-oss-120b` (RAGAS). Retrieval is local (Chroma + MiniLM), top 3 passages.

## Result: NOT YET (2 of 4 metrics improved by at least 15%)

| Metric | v1 baseline | v2 optimised | Change | Meets +15%? |
|---|---|---|---|---|
| faithfulness | 0.795 | 0.917 | +15.3% | yes |
| answer_relevancy | 0.847 | 0.819 | -3.3% | no |
| context_precision | 0.825 | 0.992 | +20.2% | yes |
| context_recall | 0.875 | 0.975 | +11.4% | no |

## What changed from v1 to v2

- Chunking: v1 cuts every 400 characters. v2 keeps one chunk per document section, with the document title and heading in front.
- Search: v1 uses vector search only. v2 merges vector search and keyword (BM25) search with reciprocal rank fusion.
- Prompt: v2 tells the model to answer only from the context, quote exact numbers and say when it doesn't know.

## Notes

- The change is relative to v1: (v2 - v1) / v1. A v1 score that is already high leaves little room to improve.
- Judge and answer models are both small Groq models, so scores are indicative, not absolute. The same judge scored both versions.
- Per-query scores are in `docs/ragas-results.csv` and in Langfuse (score names are the metric names, traces are tagged `rag-v1` / `rag-v2`).
- Example trace: https://us.cloud.langfuse.com/project/cmwtajhs500evad0dvsmhsd74/traces/f89426eca9068fda71e5228e3b60dd50
