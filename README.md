# Team Accenture — Strangler Fig

## Participants
- Tomasz Skibicki (PM / Architect / Dev / Tester / Platform)

## Scenario
Scenario 1: Code Modernization

---

## What We Built

A full Strangler Fig extraction of the Spring Music monolith — a Spring Boot 2.4 application with
JPA, MongoDB and Redis backends behind a single CrudRepository abstraction, an AngularJS 1.x SPA,
and Cloud Foundry-specific startup wiring. The monolith was non-trivial: it didn't compile on Java 22
out of the box, had no meaningful test coverage, and carried JPA annotations mixed into the domain model.

We upgraded the build chain (Spring Boot 3.2.5 / Gradle 8.9 / Jakarta EE), wrote 22 characterization
tests pinning all existing behavior (bugs included), extracted the Album Catalog Service as a Python
FastAPI service with 25 contract tests, and wrapped the whole thing in a layered safety net: a
PreToolUse hook that hard-blocks JPA leakage at authoring time, fence tests that catch it at runtime,
a scorecard eval harness that measures Claude's seam-identification accuracy, a rehearsed cutover
runbook, and a 5-agent parallel risk analysis.

Everything that runs is actually running: both test suites are green, the fence hook fires on every
write, the scorecard eval produces real metrics from the real API, and the cutover rehearsal passed GO.

---

## Challenges Attempted

| # | Challenge | Status | Notes |
|---|-----------|--------|-------|
| 1 | The Stories | skipped | BYO monolith used; domain already understood |
| 2 | The Patient | skipped | Used Spring Music BYO repo |
| 3 | The Map | done | ADR-001 with 5 seams ranked by risk, "what we chose NOT to do" section, 3-level CLAUDE.md |
| 4 | The Pin | done | 22 characterization tests; build chain upgraded from SB 2.4 → 3.2.5 to run on Java 22 |
| 5 | The Cut | done | Python FastAPI service, 25 contract tests, both suites green on same commit |
| 6 | The Fence | done | PreToolUse hook + 16 fence tests (API / OpenAPI / AST) + ADR-002 |
| 7 | The Scorecard | done | 5-candidate golden set, eval harness via claude CLI, 100% accuracy, 0% false-confidence |
| 8 | The Weekend | done | Cutover runbook with rollback triggers + rehearse.py; rehearsal passed GO |
| 9 | The Scouts | done | 5 parallel subagents, 3/5 full agreement with ADR-001, 2 divergences analysed |

---

## Key Decisions

**1. Python FastAPI over Spring Boot 3 for the new service.**
The point of the extraction is to cross the language boundary cleanly. A Java service would
carry the temptation to copy-paste the JPA model. Python forces a rewrite, which is the correct
behavior for an anti-corruption layer. The fence hook enforces this at authoring time.

**2. PreToolUse hook instead of (or in addition to) CLAUDE.md instruction.**
CLAUDE.md expresses preferences — a sufficiently persuasive prompt can override it. A hook
that exits with code 2 cannot be argued with. ADR-002 documents this distinction explicitly.
Both layers exist: hook for authoring-time enforcement, fence tests for runtime regression.

**3. Characterization tests pin bugs, not correctness.**
The monolith returns HTTP 200 + empty body for missing albums. That is a bug, but it is the
current behavior. The characterization suite pins it. The new service fixes it (404). The
contract tests document the deliberate divergence. Both are green at the same time — the
delta is explicit and trackable.

**4. Scorecard eval via claude CLI fallback.**
Claude Code doesn't expose ANTHROPIC_API_KEY to subprocesses. The eval harness falls back
to `claude -p` (already authenticated) rather than requiring the user to manage API keys.
This makes the scorecard runnable in any Claude Code session without extra setup.

**5. Scouts: explicit context in every subagent prompt.**
Task subagents don't inherit coordinator context. Each of the 5 scout prompts was fully
self-contained: file paths, scoring rubric, output format. The two divergences from ADR-001
both trace to missing dimensions in the prompt (operational overhead, strategic sequencing)
— documented in `scouts/comparison.md` with suggested prompt fixes.

---

## How to Run It

**Prerequisites:** Java 17+, Python 3.11+, Gradle (wrapper included), `pip install fastapi uvicorn pytest httpx`.

```bash
# Run both test suites (characterization + contract) — must be ALL GREEN
run-tests.bat

# Run fence tests only
cd album-catalog-service
python -m pytest tests/test_fence.py -v

# Run scorecard eval (uses claude CLI auth)
python scorecard/eval.py --skip-behavior

# Cutover rehearsal (starts live service, runs smoke tests, reports GO/NO-GO)
python cutover/rehearse.py

# Run Scouts (5 parallel subagents — requires Claude Code session)
# Launch from within Claude Code — see scouts/results.json for last run output
```

---

## If We Had More Time

1. **Challenge 1 — The Stories.** User stories with explicit stakeholder disagreements captured
   (404 fix vs. backwards compatibility, albumId retention vs. deletion, multi-DB vs. single backend).
   The disagreements surfaced during characterization — they should be written up as PM artifacts.

2. **Prometheus metrics on the new service.** The cutover runbook references error rate and p99
   latency thresholds but there's nothing emitting them. A `/metrics` endpoint with request count
   and latency histograms would make the monitoring window in STEP 5 of the runbook actionable.

3. **Scouts prompt improvement.** Add two scoring dimensions: `operational_overhead` (cost of
   running a new deployable unit) and `strategic_sequencing_value` (is this the lowest-friction
   first win?). These were the root cause of both divergences from ADR-001.

4. **Docker Compose.** `docker-compose.yml` with the Album Catalog Service and an nginx reverse
   proxy in front of both services — makes the cutover STEP 4 (traffic routing) executable locally
   rather than described in prose.

5. **CI integration.** `run-tests.bat` + `scorecard/eval.py --dry-run --skip-behavior` as a
   GitHub Actions workflow. The scorecard dry-run is fast (no API calls) and validates that the
   golden set and harness haven't drifted.

---

## How We Used Claude Code

**What worked best:**

- **Three-level CLAUDE.md** paid off immediately. Ground rules written once in Challenge 3 held
  throughout — Claude never tried to modify the monolith without characterization tests, and
  never suggested copying JPA annotations into the new service.

- **PreToolUse hook as a hard guardrail.** The fence hook caught authoring mistakes before they
  reached the filesystem. This is qualitatively different from a prompt: it cannot be argued
  away by context.

- **Parallel subagents (The Scouts).** Five agents running in a single message, each with
  fully explicit context, returned independent risk assessments in under 30 seconds. The
  divergences from the human ADR were as informative as the agreements — they revealed exactly
  which dimensions agents can't score without being explicitly asked.

- **Characterization-first discipline.** Having Claude write tests that pin existing behavior
  (including bugs) before touching any source created a safety net that held for the rest of
  the scenario. Every subsequent change was made with confidence.

**What surprised us:**

- The scorecard eval showed 100% accuracy on seam classification. We expected at least one
  wrong verdict given the ambiguity of `platform_info` vs `error_endpoints`. The model read
  `System.exit()` in ErrorController and independently recommended DELETE — without being told
  what the ADR said.

- The build chain upgrade from Spring Boot 2.4 to 3.2.5 required more archaeology than expected
  (javax→jakarta, deprecated YAML keys, missing interface methods in Spring Data 3). Claude handled
  all of it without being told what to look for — it read the error messages and traced the causes.

**Where it saved the most time:**

Writing 22 characterization tests against an undocumented API in one pass. Manually, that would
have required reading every controller method, running the app, probing edge cases by hand, and
writing assertions. Claude read the source, identified the edge cases (including the 200+empty bug),
and generated tests that pinned all of them — in a single session.
