# ADR-001: Strands agent on Groq (via LiteLLM) instead of Bedrock

**Status:** Accepted   **Date:** 2026-11-19   **Feature:** onboarding-buddy-m1

## Context
Gate G-1 needs a Strands agent behind a streaming API. The plan assumes Bedrock, but the new AWS account has
Bedrock quotas at 0. Groq free tier (openai/gpt-oss-120b) works today.

## Decision
Use Strands `Agent` with `LiteLLMModel("groq/<model>")`. The model is created in one method, `Assistant.init_llm_model`,
so moving to Bedrock later means replacing only that method (Strands has `BedrockModel`).

## Alternatives
| Option | Why not |
|---|---|
| Keep LangChain and hand-roll tool calls | Not a Strands agent; misses the gate |
| Strands + Bedrock now | Quota is 0; would block the milestone |

## Consequences
- Good: free, no AWS dependency, tests run offline with a fake model.
- Bad: Bedrock Guardrails (Week 8) not available; reasoning_effort/num_retries passthrough to Groq is untested live.
