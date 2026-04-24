# ADR-002: Anti-Corruption Layer — PreToolUse Hook vs. Prompt Instruction

**Status:** Accepted  
**Date:** 2026-04-24  
**Deciders:** Architecture team

---

## Context

During the Strangler Fig extraction of the Album Catalog Service, we need to ensure that
Spring/JPA/Hibernate implementation details from the monolith never enter the new Python service.
The question is how to enforce this boundary.

Two mechanisms are available in Claude Code:

1. **Prompt instruction** — add a rule to CLAUDE.md: "never use JPA annotations in album-catalog-service/"
2. **PreToolUse hook** — a script that intercepts every `Write` and `Edit` before it reaches the filesystem
   and exits with code 2 (blocking) if forbidden patterns are detected

---

## Decision

We use a **PreToolUse hook** (`fence-check.py`) as the primary enforcement mechanism,
supplemented by **pytest tests** in `test_fence.py` as a regression net.

CLAUDE.md still documents the rule, but CLAUDE.md alone is not sufficient.

---

## Rationale

### Why a hook is stronger than a prompt

| Property | Prompt / CLAUDE.md | PreToolUse hook |
|---|---|---|
| Can be overridden by context | Yes — a persuasive prompt can talk past it | No — exit code 2 is final |
| Enforces at authoring time | No | Yes — blocks the file write |
| Visible to future developers | Yes (documentation) | Yes (code in `.claude/hooks/`) |
| Testable | No | Yes (pipe mock stdin, check exit code) |
| Scope | Preference | Hard rule |

A prompt says "I'd prefer you don't do this." A hook says "you cannot do this."

For the ACL boundary, "I'd prefer" is not strong enough. A JPA annotation in the Python service
is not a style violation — it is categorically wrong (Java annotations don't execute in Python)
and signals that the monolith's domain model is bleeding across the boundary.

### Why we also keep pytest tests

The hook prevents authoring mistakes. But the API contract can still be violated at runtime
by indirect means — for example, if serialization configuration accidentally emits a `_class`
field copied from MongoDB, or if a field name is copied verbatim from the Java domain class.

`test_fence.py` covers:
- **API response fence** — no JPA/Spring/Java strings in HTTP responses
- **OpenAPI schema fence** — no Java type references in the public contract
- **Source code fence** — static `ast.parse()` scan of `main.py` for forbidden identifiers

Both layers are needed: the hook is a hard stop, the tests are a regression net.

---

## Consequences

- Any `Write` or `Edit` targeting `album-catalog-service/` is intercepted
- If the content contains patterns from `FORBIDDEN_PATTERNS`, the write is blocked with a
  descriptive error message naming the specific violation
- The fence script is at `.claude/hooks/fence-check.py` and is checked into source control
- Developers working without Claude Code (plain editors) are covered by `test_fence.py` in CI
- The hook adds ~5ms overhead per file write — negligible

---

## Alternatives Considered

### CLAUDE.md instruction only
Rejected. Prompts are overridable by context. Authoring-time enforcement requires a hard stop.

### Post-commit git hook
Rejected. Too late — the violation is already in source. PreToolUse catches it before the file exists.

### Separate linter (flake8 plugin)
Considered. Would work but requires installing a custom plugin. The PreToolUse hook is
self-contained and does not require changes to the project's Python toolchain.
