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
