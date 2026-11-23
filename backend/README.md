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
powershell -File deploy\stack-up.ps1            # one-time: create the box, API, k3s, Fission, welcome function
powershell -File deploy\orchestrator-setup.ps1  # one-time: Step Functions state machine behind demo-up/down
powershell -File deploy\demo-down.ps1           # stop the box (saves money)
powershell -File deploy\demo-up.ps1 -Hours 3    # start it for a demo, firewall opens to your current IP, stops by itself after 3 h
powershell -File deploy\measure-cold-start.ps1 -Ip <ip>   # cold vs warm timings, appended to docs\cold-start.csv
```

The public IP changes on every start, `demo-up` prints it. Fission function: `POST http://<ip>:31314/welcome` with `X-API-Key` and `{"name": "Asha", "role": "developer"}`.
Don't re-save `backend\.env` with PowerShell `Set-Content -Encoding utf8` (it adds a hidden BOM that breaks the Kubernetes secret). Use an editor, or `[IO.File]::WriteAllText` with `UTF8Encoding($false)`.
