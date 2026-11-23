# Architect: onboarding-buddy-m1
- Two files do the work: `backend/onboarding_tools.py` (plain tool functions + sample data) and `backend/main.py` (Assistant class, SSE routes).
- Flow: POST /chat/stream -> new Assistant -> Strands Agent -> (tools) -> text events -> SSE `data:` lines -> `event: done`.
- Failure mode: any exception becomes an SSE `error` event (existing behaviour, kept).
- See ADR-001. Design: .10x/specs/2026-11-19-onboarding-buddy-m1-design.md
