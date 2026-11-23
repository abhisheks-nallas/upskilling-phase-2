# Onboarding Buddy: backend (Milestone 1)

A chat assistant that helps a new joiner through their first 30 days. FastAPI streams the answer (SSE);
a Strands agent decides when to call its two tools.

## Tools
- `build_30_day_plan(role, start_date)`: day-by-day plan, weekends skipped, light first week.
- `get_access_checklist(role)`: tools and access needed for the role.

Roles: developer, qa, ba, pm. The data is sample data in `onboarding_tools.py`.

## Run
```
pip install -r requirements-dev.txt
copy .env.example .env      # then put your Groq key in .env
uvicorn main:app --reload
```

## Choose the model backend
Set in `backend/.env` (git-ignored; copy `.env.example`):
- `LLM_PROVIDER=groq` (default) uses `GROQ_FREE_MODEL` (free tier: `openai/gpt-oss-20b`).
- `LLM_PROVIDER=bedrock` uses `BEDROCK_MODEL_ID` in `AWS_REGION`. Claude Sonnet 5.5 is listed in ap-southeast-2 as the
  `au.anthropic.claude-sonnet-5-5` profile (calls fail until AWS finishes verifying the account).
  AWS keys can go in the same `.env` or come from your AWS CLI profile.

## Try it
```
curl -N -X POST localhost:8000/chat/stream -H "Content-Type: application/json" -H "X-API-Key: YOUR_API_KEY" ^
  -d "{\"message\": \"I am a QA joining on 2026-12-07. What access do I need, and what is my first week?\"}"
```
API spec: http://localhost:8000/docs (use the Authorize button to enter your API key)
`API_KEY` in `.env` is the password for `/chat/stream`; without it every request is rejected. `/health-check` is open.

## Test (no key or internet needed)
```
pytest
```

## Deploy to AWS (Sydney)
```
powershell -File ..\deploy\deploy-ec2.ps1     # one EC2 instance + Docker, reachable only from your IP
powershell -File ..\deploy\update-ec2.ps1     # push new code or .env to the running instance (no firewall changes)
powershell -File ..\deploy\teardown-ec2.ps1   # removes everything it created
```

## Plan agents (Milestone 2)

`POST /plan/stream` (needs `X-API-Key`) runs a LangGraph of two agents: a **Planner** that rewrites the template 30-day plan for the role, and a **Reviewer** that checks it (dates, day 1 = access setup, tone). A rejected draft goes back to the Planner with feedback, up to 3 drafts, then the plain template is returned (`"source": "fallback"`).

```
curl -N -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"role":"developer","start_date":"2026-12-01","spoil_first_draft":true}' http://localhost:8000/plan/stream
```

Events: `progress` (planner / reviewer / fallback steps), `result` (the plan and its `source`), `done`, `error`.
`spoil_first_draft` is a demo switch: it damages the first draft so you can show the Reviewer catching it and the retry fixing it.
Tracing goes to LangSmith when the `LANGSMITH_*` settings are in `.env`. Tests switch tracing off.

## Milestone 2 staging on AWS (c7i-flex.large: API + k3s + Fission)

```
powershell -File deploy\push-image.ps1          # build the image here, push to ECR as :latest
powershell -File deploy\push-secrets.ps1        # upload backend\.env to Parameter Store (re-run after every .env change)
powershell -File deploy\stack-up.ps1            # one-time: create the box, API, k3s, Fission, welcome function
powershell -File deploy\orchestrator-setup.ps1  # one-time: Step Functions state machine behind demo-up/down
powershell -File deploy\demo-down.ps1           # stop the box (saves money)
powershell -File deploy\demo-up.ps1 -Hours 3    # start it for a demo, firewall opens to your current IP, stops by itself after 3 h
powershell -File deploy\measure-cold-start.ps1 -Ip <ip>   # cold vs warm timings, appended to docs\cold-start.csv
```

The public IP changes on every start, `demo-up` prints it. Fission function: `POST http://<ip>:31314/welcome` with `X-API-Key` and `{"name": "Asha", "role": "developer"}`.
The box never gets `.env` copied to it. At every boot it fetches the encrypted Parameter Store value `/upskilling-p2/onboarding-buddy/env` (Docker's `.env` and the Fission secret). After changing `backend\.env`, run `push-secrets.ps1` and the next `demo-up` uses the new values.
Don't re-save `backend\.env` with PowerShell `Set-Content -Encoding utf8` (it adds a hidden BOM that breaks the Kubernetes secret). Use an editor, or `[IO.File]::WriteAllText` with `UTF8Encoding($false)`.

## Company knowledge search (Milestone 3)

The chat agent has a third tool, `search_company_docs(question)`, for policy questions (leave, expenses, IT, security, benefits...). The sample documents are in `knowledge/*.md` and are made up for the demo. Replace them with real ones and re-run the evaluation.

The search runs inside the API process, nothing extra to deploy: documents are split into chunks, embedded with Chroma's small built-in model (MiniLM via onnx, CPU, no API key) and kept in memory. It is rebuilt at start up, which takes about a second.

Two versions of the pipeline live in `rag.py` so we can measure what the changes buy us:
- **v1 (baseline):** fixed 400-character chunks, vector search only, plain prompt.
- **v2 (used by the chat tool):** one chunk per document section with the title in front, vector and keyword (BM25) results merged, a prompt that says "answer only from the context".

Tracing: `retrieval`, `generation` and the whole `rag-query` are sent to Langfuse when the `LANGFUSE_*` keys are in `.env`. Traces are tagged `rag-v1` or `rag-v2`. Tests switch it off.

## Measure RAG quality (G-3)

```
backend\.venv\Scripts\python.exe tools\rag_eval.py --limit 20      # 20 questions through v1 and v2, scored with RAGAS
```
It writes `docs/ragas-report.md` (before vs after for faithfulness, answer relevancy, context precision, context recall), `docs/ragas-results.csv` (every question) and posts the scores to Langfuse, so the dashboard shows them per query.
The Groq free tier allows 8,000 tokens a minute and 200,000 a day, and RAGAS judge calls are token-hungry, so the script waits between calls and saves its progress. If the daily limit stops it, run the same command again later. Use `--fresh` after changing documents, questions or RAG code.
