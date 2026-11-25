# Onboarding Buddy: Product Requirements Document (BMAD cycle, Wk 5 artefact)

Status: AI-drafted from the existing design doc, ADRs and the built system. **Waiting for peer review** (see the review table at the end).
Stand-in note: real client backlog items are confidential, so the BMAD cycle is run on this internal feature. The steps and artefacts are the same.

## 1. Business and problem
New joiners spend their first weeks asking the same questions (leave, expenses, laptop, who to ask) and waiting for a plan of what to do when.
HR and team leads answer these by hand. Answers are inconsistent and wrong numbers cause real confusion.

## 2. Goals and non-goals
Goals
- A new joiner gets a correct, sourced answer to a policy question in seconds.
- A new joiner gets a 30-day plan for their role and start date.
- Quality is measured (RAGAS) and a quality drop blocks a release.
- Every model call is traceable (latency, tokens, cost).

Non-goals (this sprint)
- Real client data, real HR systems, single sign-on, a web UI, multi-turn memory, public-holiday calendars.

## 3. Users
| User | Need |
|---|---|
| New joiner | Fast, correct answers and a clear plan |
| HR / team lead | Fewer repeat questions, one source of truth |
| QA / tech lead | Evidence that quality does not regress |

## 4. Requirements
Functional
| ID | Requirement |
|---|---|
| FR-1 | `POST /chat/stream` streams an answer as server-sent events. |
| FR-2 | The agent can build a 30-day plan for a role and start date, and list the access a role needs. |
| FR-3 | Policy questions are answered only from the company documents, quoting exact numbers, and say "I don't know" when the documents do not cover it. |
| FR-4 | `POST /plan/stream` runs a two-agent draft and review loop and streams each step. |
| FR-5 | Every endpoint except `/health-check` needs an API key. |
| FR-6 | Off-limits requests (prompt injection, prompt leaks, over-long input) are refused with a standard message and never reach the model. Answers never show key- or ID-shaped text. |

Non-functional
| ID | Requirement |
|---|---|
| NFR-1 | Answer quality: faithfulness, answer relevancy, context precision and context recall measured on at least 20 questions. |
| NFR-2 | CI blocks a pull request when any RAGAS metric drops more than 10% below the baseline. |
| NFR-3 | p95 latency of a chat query is alerted when over 8 seconds. |
| NFR-4 | Runs on one small server with free-tier models. Compute cost only while demoing. |
| NFR-5 | Secrets live in a git-ignored `.env` locally and in Parameter Store on the server. |

## 5. Epics and stories
| Epic | Story | Acceptance criteria |
|---|---|---|
| E1 Chat | As a joiner I ask a question and see the answer appear as it is written | Given a valid key, when I post a question, then I receive `data:` events and a final `done` event |
| E1 Chat | As a joiner I get a plan for my role | Given role QA and a start date, then the plan has 30 calendar days, skips weekends, and day 1 is access setup |
| E2 Knowledge | As a joiner I ask about leave | Given the leave question, then the answer quotes the number of days from the document and does not invent others |
| E2 Knowledge | As a joiner I ask something the documents do not cover | Then the answer says it does not know and suggests asking HR |
| E3 Safety | As the company I refuse prompt-injection attempts | Given "ignore all previous instructions", then the standard refusal is returned and the model is not called |
| E4 Quality | As a tech lead I want bad prompts blocked | Given a PR that degrades the prompt, then the CI check fails and shows which metric dropped |
| E4 Quality | As an operator I want a latency alert | Given p95 over the limit, then the scheduled check fails |

## 6. Success measures
- RAGAS v2 scores on the 20-question set, reported against the v1 baseline.
- CI gate: good change passes, degraded change fails.
- Zero open P1 defects at sprint end.

## 7. Risks and open points
- Free-tier model limits slow evaluation (Groq daily tokens).
- A small LLM judge makes scores noisy at 20 questions.
- The +15% improvement target is hard to reach when v1 recall is already high (G-3 not met).
- Guardrails are pattern-based and can be bypassed by rephrasing.

## 8. Peer review
| Reviewer | Date | Comments | Approved |
|---|---|---|---|
| | | | |
