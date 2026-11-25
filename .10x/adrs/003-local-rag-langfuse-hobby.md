
# ADR-003: Local RAG (Chroma) and Langfuse Cloud Hobby for Milestone 3

**Status:** Accepted
**Date:** 2026-11-23
**Feature:** rag-quality (G-3)
**Author:** 10x-Team (Architect + Staff Engineer)

## Context
G-3 needs a RAG pipeline, a before/after RAGAS comparison (at least 15% better on at least 3 of 4 metrics) and a Langfuse dashboard with per-query metrics. There was no RAG and no baseline yet. The project is built the cheapest MVP way, and Bedrock is still blocked by account verification.

## Decision
- Retrieval runs inside the API process: Chroma in memory, Chroma's built-in onnx MiniLM embeddings, documents in `backend/knowledge/*.md`. v1 is the naive baseline, v2 the optimised version (section chunks, vector + BM25 merged, stricter prompt). Both live in `backend/rag.py`.
- Langfuse Cloud Hobby (free: 50k units/month, 30 days, 2 users) for traces and scores. RAGAS runs from `tools/rag_eval.py`, judge = Groq `gpt-oss-120b`.
- Evaluation results are also written to `docs/ragas-report.md` and `docs/ragas-results.csv` so the evidence outlives Langfuse's 30-day retention.

## Alternatives Considered
| Alternative | Pros | Cons | Why Not |
|-------------|------|------|---------|
| Bedrock Knowledge Base + S3 Vectors | Managed, pennies with S3 Vectors (no idle minimum), good panel story | Bedrock access still blocked; S3 Vectors was the slowest store in one benchmark; ingestion jobs to manage | Cannot be used today. `retrieve()` can get a Bedrock backend later |
| Bedrock KB + OpenSearch Serverless | Default, fast | About $350 to $700 a month minimum | Far too expensive for an MVP |
| sentence-transformers + FAISS | Popular | Pulls in torch, about 1 GB more in the image | Chroma's onnx model is enough for ten documents |
| Self-hosted Langfuse | No limits | Needs ClickHouse and Postgres, roughly $95 a month in one estimate, would crowd the 4 GB box | Cloud Hobby is free and the usage is far below 50k units |

## Consequences

### Positive
- Costs nothing extra, nothing new to deploy, works offline apart from the LLM.
- v1 and v2 share one interface, so the comparison is fair and a Bedrock backend can be added later.

### Negative
- Index is rebuilt at every start and held in memory, fine for ten documents, not for thousands.
- The embedding model is downloaded into the Docker image at build time (about 80 MB).
- Groq free tier (8K tokens a minute, 200K a day) makes a full RAGAS run slow and possibly multi-day. Judge and answer models are small, so scores are indicative.
- Hobby keeps data 30 days and allows 2 users.

### Risks
- Synthetic documents and questions written by the same author flatter retrieval. Replace with real documents before quoting the numbers outside the programme.

## Dependencies
- Groq key, Langfuse keys in `backend/.env` (also pushed to Parameter Store by `deploy\push-secrets.ps1`).

## Update 2026-11-25: evaluation set extended, local judge
- With 11 short documents v1 already scored 0.875 on context recall, so +15% was impossible (the maximum gain is +14.3%). The corpus was extended with 6 longer documents and a new 20-question set was written before scoring. v1 and v2 code were not changed. The change is disclosed here because it was made after seeing a first result.
- The Groq free tier (200K tokens a day per model) could not score 20 questions twice in a day, so the judge is now a local Qwen3-14B (Q4_K_M, llama.cpp, kept on D:). Judge and answer models are different families, which avoids a model grading its own answers. Scores from different judges are not comparable, and the report names the judge.
- Result on the extended set: 2 of 4 metrics improve by at least 15%. G-3 is not met.
