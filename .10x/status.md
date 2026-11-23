# Status
- Milestone 1 (G-1): code + tests done, awaiting developer review and a live Groq run.
- Open for G-1: deploy somewhere, commit, record the demo.
- Next: Milestone 2 (two agents + Fission).

## 2026-11-23 AWS check
- AWS creds work (account <account-id>, user agent-user, region ap-south-1) from the developer's PC.
- Organization SCP explicitly denies S3 (CreateBucket, ListBuckets) and EC2 (DescribeInstances) and SSM GetParameter. Needs the org admin.
- Bedrock lists Sonnet 5.5, but invoking returns "account is being verified" (AccessDeniedException).
- LLM provider is now switchable: LLM_PROVIDER=groq|bedrock (16 tests pass, also in the Windows venv).

## 2026-11-23 Deployed (Milestone 1)
- Running on EC2 t3.small, ap-southeast-2, in Docker (instance i-0e1736c9e055b98cf, http://16.179.89.189:8000, /docs for the API spec).
- Model: Groq openai/gpt-oss-20b. LLM_PROVIDER=bedrock is ready but blocked until AWS finishes verifying the account.
- Live test from the developer's PC: /health-check ok; a QA onboarding question streamed 172 events with both tools' data, ended with `done`, ~3s.
- Firewall allows only the developer's IP at deploy time. No HTTPS, no login. Teardown: deploy\teardown-ec2.ps1.
- Not yet: git commit/push, demo recording.

## 2026-11-23 API key added
- /chat/stream now needs the X-API-Key header (value is API_KEY in backend/.env, also on the server). /health-check and /docs stay open.
- No key configured on the server = every chat request rejected. 19 tests pass.
- Firewall unchanged (developer's IP only). Developer demos from their own PC over screenshare.
- Push code/.env changes with deploy\update-ec2.ps1.

## 2026-11-23 Milestone 2 (G-2) built
- LangGraph Planner + Reviewer (`backend/plan_graph.py`, `POST /plan/stream`): retry up to 3 drafts, then template fallback. Demo switch `spoil_first_draft`. 28 tests pass, tests never call Groq or LangSmith. Verified live against Groq and on the cloud box.
- LangSmith tracing is on through `LANGSMITH_*` in backend/.env (agent id + environment). Do not also set LANGSMITH_PROJECT, the two conflict and traces stop.
- One c7i-flex.large box (`upskilling-p2-stack`, Sydney, 30 GB disk, 2 GB swap) runs the API in Docker, k3s and Fission. Images are built on the PC and pulled from ECR (`deploy\push-image.ps1`, `:latest`). Measured: 1.4 GB used of 4 GB with everything running. The old t3.small is stopped, not terminated.
- Fission `welcome` function (`fission/welcome/welcome.py`, `POST :31314/welcome`, needs X-API-Key). Cold start measured: ~1.3 s cold vs ~1.16 s warm, rows in `docs/cold-start.csv`.
- Start/stop: Step Functions state machine `upskilling-p2-demo-session` (no Lambda). `deploy\demo-up.ps1 -Hours N` starts the box, points its firewall at the caller's current IP, waits for the API and Fission (49 s in the test), and the box stops by itself after N hours. `deploy\demo-down.ps1` stops it now. The public IP changes on every start, the script prints the new one.
- Gotchas hit: Fission chart 1.27.0 does not install its CRDs (apply them first, `remote-k3s.sh` does); a UTF-8 BOM in backend/.env broke the Kubernetes secret keys (never re-save .env with Windows PowerShell `Set-Content -Encoding utf8`).
- Not yet: Bedrock (account still being verified), M1/M2 demo recordings.
