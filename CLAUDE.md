# Claude Code Hackathon — Scenario 1: Code Modernization

## Project Overview

We are modernizing the Spring Music monolith (`spring-music-master/`) using the **Strangler Fig pattern**.  
The new Album Catalog Service will live in `album-catalog-service/` (to be created in Challenge 5).

## Decomposition Plan

See [ADR-001](spring-music-master/docs/adr/001-decomposition-plan.md) for the full decomposition plan.

**Extraction order:**
1. Frontend SPA → nginx container
2. Album Catalog Service → new service (Spring Boot 3 or FastAPI)
3. Replace CF profile initializer with 12-factor env config
4. Decommission monolith

## Ground Rules

- **Never modify the monolith before characterization tests (The Pin) are green.**
- **Never let monolith domain model annotations leak into the new service's API.**
- The monolith stays alive throughout — the new service is additive, not a replacement until proven.
- `ErrorController` (`/errors/*`) is scheduled for deletion — do not build on it.
- `SpringApplicationContextInitializer` is high-risk — do not touch unless explicitly instructed.

## Directory Structure

```
claude-hackathon/
├── spring-music-master/     # Legacy monolith — handle with care
│   ├── docs/adr/            # Architecture decisions
│   └── src/                 # Source — read characterization tests before editing
└── album-catalog-service/   # New service (created in Challenge 5)
```

## Challenge Progress

- [x] Challenge 1 — The Stories (5 user stories, acceptance criteria, 7 explicit stakeholder disagreements → [stories.md](stories.md))
- [x] Challenge 3 — The Map (ADR + CLAUDE.md)
- [x] Challenge 4 — The Pin (22 characterization tests, all green)
- [x] Challenge 5 — The Cut (album-catalog-service/ extracted, 25 contract tests green)
- [x] Challenge 6 — The Fence (PreToolUse hook + 16 fence tests + ADR-002)
- [x] Challenge 7 — The Scorecard (5-candidate golden set, eval harness, 100% accuracy, 0% false-confidence rate)
- [x] Challenge 8 — The Weekend (cutover runbook + rehearse.py, rehearsal passed GO)
- [x] Challenge 9 — The Scouts (5 parallel subagents, 3/5 full agreement with ADR-001, 2 divergences analysed)

## Running All Tests

```
run-tests.bat
```

Runs both suites and exits 0 only if ALL GREEN.
