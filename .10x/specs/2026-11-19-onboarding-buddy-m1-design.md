# Onboarding Buddy, Milestone 1 (Gate G-1) design

## Why
Gate G-1 (Week 2) needs: a FastAPI endpoint that streams (SSE), and a Strands agent with 2 tools,
callable through the API, committed to the repo. The agent is "Onboarding Buddy": it helps a new
joiner with their first 30 days. Chosen with the developer earlier in the conversation.

## Goals
- `POST /chat/stream` streams the agent's answer as SSE.
- Two tools the agent can call: `build_30_day_plan`, `get_access_checklist`.
- Tests that run offline (no Groq, no key) and pass.
- Keep the developer's existing code style in `backend/main.py`.

## Non-goals (later milestones)
RAG, two-agent review loop, Fission, Langfuse/LangSmith, CI gate, Docker, deployment, public holidays.

## Approaches considered
| Option | Trade-off | Decision |
|---|---|---|
| A. Strands agent, Groq model through LiteLLM | Meets "Strands" requirement, works on free Groq, no AWS needed | **Chosen** |
| B. Keep LangChain, hand-roll a tool loop | Less new code, but not a Strands agent, so it misses the gate | Rejected |
| C. Strands + Bedrock | What the plan assumes, but Bedrock quota is still 0 | Rejected for now; swap `init_llm_model` later |

## Design
- `backend/onboarding_tools.py`: two plain `@tool` functions. Sample data lives in module-level dicts.
- `backend/main.py`: same `Assistant` class as before (`init_llm_model`, `init_agent`, `generate_response`,
  `sse_events`), now backed by a Strands `Agent`. Routes unchanged: `/health-check`, `/chat/stream`.
- Tests in `backend/tests/`: tools directly, SSE wrapper and route with a fake model.

## My calls (not yet confirmed by the developer)
- Roles supported: developer, qa, ba, pm (with a few aliases). Unknown role returns an error message.
- 30 calendar days from the start date, weekends skipped. Public holidays are NOT skipped.
- Day 1 is access setup; week 1 is reading and setup only (the "lighter first week").
- A new `Assistant` per request, so conversations do not share memory.
- `config.py` (pydantic-settings) is left untouched and unused; `main.py` keeps `load_dotenv` and `os.environ`.
- Nothing is committed. Changes stay in the working tree for review.
