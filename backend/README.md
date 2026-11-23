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
