# ADR-002: One c7i-flex.large for API, k3s and Fission; images from ECR; start/stop with Step Functions

**Status:** Accepted
**Date:** 2026-11-23
**Feature:** onboarding-buddy-m2
**Author:** 10x-Team (Architect + Staff Engineer)

## Context
Milestone 2 needs a "staging" deployment with a Fission function, on a free plan ($140 credits for 176 days). Fission needs Kubernetes 1.32 or newer and about 4 GB. The demo is run by hand for a few hours at a time.

## Decision
One c7i-flex.large (4 GB, free-plan eligible) in Sydney runs the API in Docker and k3s with Fission next to it. Docker images are built on the developer's PC and pushed to ECR, the box only pulls `:latest` (no builds on the box). The box is stopped between demos. A Step Functions state machine (direct EC2 calls, no Lambda) starts it, waits, and stops it after N hours.

## Alternatives Considered
| Alternative | Pros | Cons | Why Not |
|-------------|------|------|---------|
| t3.small for API + c7i-flex.large for k3s/Fission | Isolation | Two boxes to start/stop and pay for | Measured 1.4 GB used of 4 GB on one box |
| m7i-flex.large (8 GB) for everything | Headroom | ~16% more per hour | Not needed given the measurement |
| minikube | Familiar | Needs a VM or Docker layer on top, heavier | k3s is lighter and runs as a normal service |
| EKS | Managed | Control plane costs about $0.10/h even when idle | Does not fit the credit budget |
| Lambda instead of Step Functions | Flexible | Code to write and maintain | The state machine needs no code |

## Consequences
### Positive
- One thing to start and stop. Compute cost only while demoing (about $0.11/h).
- The box comes back by itself after a stop: API (Docker restart policy), k3s and Fission (systemd).
### Negative
- Public IP changes every start; the scripts print it and re-point the firewall at the caller's IP.
- No HTTPS, API key only, firewall limited to one IP. Fine for a demo, not for users.
### Risks
- 4 GB is enough today (2 GB of it free). Heavier models or more functions may need m7i-flex.large.
- k3s and Helm are installed from their official install scripts at stack-up time (not pinned for k3s).

## Secrets
Secrets are one SecureString in Parameter Store, fetched by the box at every boot. Parameter Store over Secrets Manager because it is free; Secrets Manager costs about $0.40 per secret per month and adds rotation, which this demo does not need.

## Dependencies
- ADR-001 (Groq via LiteLLM). IAM roles for ECR pull and for the state machine, created in the account.
