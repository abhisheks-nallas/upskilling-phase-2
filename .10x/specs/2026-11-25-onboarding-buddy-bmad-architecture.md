# Onboarding Buddy: Architecture (BMAD cycle, Wk 5 artefact)

Status: AI-drafted from the built system. **Waiting for peer review.** Follows the PRD in `2026-11-25-onboarding-buddy-bmad-prd.md`.
Decisions in more depth: ADR 001 (Strands with Groq), ADR 002 (single box, k3s, Fission, ECR), ADR 003 (local RAG, Langfuse Hobby).

## 1. Overview
```
client --HTTPS/HTTP + X-API-Key--> FastAPI (Docker, one EC2 box)
                                     |-- guardrails (input check, output clean-up)
                                     |-- /chat/stream  -> Strands agent --tools--> plan, access list, search_company_docs
                                     |                                                   |
                                     |                                       RAG v2: Chroma (in memory) + BM25 -> top 3 sections
                                     |-- /plan/stream  -> LangGraph (draft agent, review agent, fix loop)
                                     '-- Groq gpt-oss-20b via LiteLLM (Bedrock switch ready, quota pending)
Langfuse Cloud <-- spans: rag-query > retrieval, generation (tokens, latency)
GitHub Actions: tests + RAGAS gate on PRs, Docker build, daily p95 alert
```

## 2. Components
| Component | File | Responsibility |
|---|---|---|
| API | `backend/main.py` | Routes, API key check, SSE streaming |
| Guardrails | `backend/guardrails.py` | Refuse injection, leaks and long input; hide keys and IDs in answers |
| Tools | `backend/onboarding_tools.py` | 30-day plan, access checklist, document search |
| RAG | `backend/rag.py` | v1 baseline and v2 (section chunks, vector plus BM25 fusion, strict prompt), Langfuse spans |
| Plan graph | `backend/plan_graph.py` | Draft and review agents with error recovery |
| Knowledge | `backend/knowledge/*.md` | 17 fictional company policy documents |
| Evaluation | `tools/rag_eval.py` | RAGAS over 20 questions, v1 against v2 |
| CI gate | `tools/ci_gate.py` | 6-question smoke check against `docs/ragas-baseline.json` |
| Alert | `tools/latency_alert.py` | p95 of `rag-query` spans from the Langfuse observations API |

## 3. Key decisions
| Decision | Why | Trade-off |
|---|---|---|
| In-memory Chroma, rebuilt at start | 17 small docs index in seconds, nothing to operate | Index rebuilds on every restart |
| v2 chunks follow headings | Whole policy sections stay together | Less control over chunk size |
| Local ONNX embedder | No API key, no cost | Smaller model than hosted ones |
| Pattern guardrails | Bedrock Guardrails unavailable, no cost | Can be bypassed by rephrasing |
| Gate uses 6 questions and a Groq judge | Fits the free daily token limit | Noisy, a single run can mislead |
| Alert is a scheduled workflow | Langfuse Hobby has no alerting | Checks once a day, not live |

## 4. Quality and observability
- Each request is one `rag-query` span with `retrieval` and `generation` children. Generation records input and output tokens and the model.
- Scores (faithfulness, answer relevancy, context precision, context recall) are written to Langfuse per trace.
- Cost shows as $0.00 because the free Groq models have no price in Langfuse.

## 5. Security
- API key on every route except `/health-check`, compared in constant time.
- Secrets never in git: `.env` locally, Parameter Store plus an instance role on the server.
- Firewall is open only to the developer's IP while the box runs. It stops itself after a set number of hours.
- No client data is used anywhere.

## 6. Deployment
Docker image built on the developer's PC, pushed to ECR, pulled by the box (`deploy/remote-api.sh`). A Step Functions state machine starts and stops the box. CI builds the image but does not push.

## 7. Failure modes
| Failure | Effect | Handling |
|---|---|---|
| Groq rate limit | Slow or failed answers, failed eval | Retries; the eval resumes from its cache |
| Judge noise | A good PR could fail the gate | Re-run the check; plan a pass band |
| Model refuses or errors | SSE `error` event | Client sees an error event, no crash |
| Box stopped | API unreachable | Start with `deploy/demo-up.ps1` |

## 8. Peer review
| Reviewer | Date | Comments | Approved |
|---|---|---|---|
| | | | |
