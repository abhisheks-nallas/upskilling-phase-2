# SDE: onboarding-buddy-m1
Built: both tools, Strands-backed Assistant, SSE routes, 13 offline tests (tools; fake-model agent run through the API; error event; bad input).
Verified: tests fail when the code is deliberately broken (event key, weekend rule).
Not verified: a real Groq call (sandbox could not reach api.groq.com).
Tech debt: weekends only (no holidays), sample data hard-coded, `config.py` unused, no Dockerfile/deploy yet.
