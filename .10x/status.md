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

## 2026-11-23 Secrets in Parameter Store
- backend/.env is stored as one SecureString parameter `/upskilling-p2/onboarding-buddy/env` (standard tier, free, default AWS-managed key) by `deploy\push-secrets.ps1`. Chosen over Secrets Manager on cost (about $0.40/secret/month there); same pattern, can move later.
- The box's role may read only that parameter. `sync-env.service` writes the API's .env before Docker starts, `sync-k8s.service` rebuilds the Fission secret after k3s is up. No more scp of .env.
- Proven: deleted the box's .env and the Kubernetes secret, stopped with the state machine, started with demo-up: both came back on their own, API plan stream and Fission welcome worked (ready in 50 s).
- After a key change: run push-secrets.ps1, then demo-up (or demo-down + demo-up if the box is already running).

## 2026-11-23 Milestone 3 (G-3) built, evaluated on 20 questions, gate NOT MET (2 of 4)
- Branch `milestone-3`. RAG in `backend/rag.py`, sample docs in `backend/knowledge/` (11 made-up files), 26 eval questions in `backend/eval/questions.json`. Chat agent got a third tool `search_company_docs` (v2). Decision record: `.10x/adrs/003-local-rag-langfuse-hobby.md` (local Chroma instead of Bedrock KB, Langfuse Cloud Hobby). 40 tests pass, tests never call Groq or Langfuse.
- Langfuse: `retrieval`, `generation`, `rag-query` spans, traces tagged `rag-v1`/`rag-v2`, RAGAS scores posted per trace (checked through the API, they match the local results). Langfuse Cloud removed its old trace-read API on 2026-11-16, only ingestion and the v2 APIs work.
- First RAGAS result, 11 docs and 20 easy questions, judge Groq gpt-oss-120b: faithfulness +15.3%, answer relevancy -3.3%, context precision +20.2%, context recall +11.4%. Only 2 of 4 met the bar. Recall could not reach +15% at all, because v1 already scored 0.875 (the maximum gain is +14.3%).
- Because of that ceiling, the evaluation was made more realistic (v1 and v2 unchanged): 6 longer docs added to `backend/knowledge/` (17 docs now), and a new 20-question set in `backend/eval/questions.json` (12 about the new docs, 8 reused from the old set). The old 26 questions are in `backend/eval/questions-basic.json`. The questions were written before any scoring.
- The Groq free tier kept running out (200K tokens a day per model), so the judge became a local Qwen3-14B Q4 (llama.cpp on D:\AI, `LOCAL_JUDGE_URL` option in `tools/rag_eval.py`). All 20 questions were scored in both versions with it: faithfulness 0.830 to 0.950 (+14.5%), answer relevancy 0.744 to 0.790 (+6.1%), context precision 0.742 to 0.975 (+31.5%), context recall 0.850 to 1.000 (+17.6%). G-3 NOT MET: 2 of 4 (needs 3), faithfulness is 0.5 points short. Scores from different judges are not comparable. Report: `docs/ragas-report.md`, per query: `docs/ragas-results.csv`.
- Tuning attempt, made after seeing that result: one v2 prompt change ("start with a full sentence that restates what is being asked, do not add anything the context does not say"), same judge, v1 scores reused. Faithfulness 0.913 (+10.0%), answer relevancy 0.815 (+9.5%), precision and recall unchanged, so still 2 of 4. Worse on faithfulness, so the change was reverted and the committed report is the version without it. Its extra v2 traces are still in Langfuse.
- Langfuse dashboard "RAG quality (G-3)" built by hand in the UI: average score by name for `rag-v1` and `rag-v2`, trace count, scores table.
- The G-3 sheet asks for at least 20 queries. The Groq free tier (8K tokens a minute, 200K a day) needed two days to score all 20. Progress is saved in `tools/.rag_eval_cache.json` (git-ignored); the eval resumes from it (`backend\.venv\Scripts\python.exe tools\rag_eval.py --limit 20`).
- Judge noise is real: the same answer scored faithfulness 0.0 in one probe and 1.0 in the run. Treat scores as indicative.
- Not yet: deploy the new image to the EC2 box (`deploy\push-image.ps1`, then demo-up), Bedrock backend for `retrieve()` (account still unverified).
