# ADR-001: Spring Music Decomposition Plan

**Status:** Accepted  
**Date:** 2026-04-24  
**Author:** Modernization Team

---

## Context

Spring Music is a Spring Boot 2.4.0 monolith originally built as a Cloud Foundry demo. It demonstrates multi-database patterns (JPA, MongoDB, Redis) behind a single `CrudRepository` abstraction. The board approved "modernization." This ADR defines what that means concretely, in what order, and why.

The system has one domain entity (`Album`), one REST controller (`AlbumController`), three repository implementations, CF-specific startup wiring (`SpringApplicationContextInitializer`), an AngularJS 1.2.16 SPA, and two non-business controllers (info, error).

**Goal:** Extract services safely using the Strangler Fig pattern. The monolith stays alive throughout. No big-bang rewrite.

---

## Identified Seams

| Seam | Entry Points | Coupling Level | Test Coverage | Business Criticality |
|------|-------------|----------------|---------------|---------------------|
| **Frontend SPA** | Static files in `src/main/resources/static/` | None — pure HTTP calls to `/albums`, `/appinfo` | None | High |
| **Album Catalog** | `AlbumController`, 3 repositories, `Album` entity | Spring Data `CrudRepository` abstraction | Context load only | High |
| **Platform Info** | `InfoController` (`/appinfo`, `/service`) | `CfEnv` library, Spring `Environment` | None | Low |
| **DB Profile Init** | `SpringApplicationContextInitializer` | CF internals + Spring Boot autoconfiguration | None | Infrastructure only |
| **Error Endpoints** | `ErrorController` (`/errors/*`) | None | None | None (test/chaos only) |

---

## Extraction Risk Ranking

Ranked by extraction risk, not by size.

### 1. Frontend SPA — Risk: LOW

**Why low risk:** The AngularJS app is already static files. It communicates with the backend exclusively via HTTP (`/albums`, `/appinfo`). No server-side rendering, no shared memory, no session state. The extraction is purely operational: put files behind nginx, point at the monolith's API.

**Seam test:** An HTTP integration test hitting `/albums` from outside the Spring context is sufficient to confirm the API contract holds after extraction.

**Extraction path:** Docker container running nginx serving `static/`. API calls proxied to monolith until Album Catalog Service is ready.

---

### 2. Album Catalog Service — Risk: MEDIUM

**Why medium risk:**
- Core business domain — any regression is visible to users immediately
- `Album` entity carries JPA annotations (`@Entity`, `@Id`, `@GenericGenerator`) that tangle persistence concerns into the domain model
- The `albumId` field (separate from `id`) is undocumented — its purpose is unclear and it may have implicit semantics
- Multi-database switching via Spring profiles is the entire point of the current architecture; replacing it requires a conscious decision about which database the new service owns
- No meaningful test coverage — characterization tests (The Pin) must be written before this extraction begins

**Seam test:** Characterization suite against the monolith's `/albums` endpoints (GET all, GET by ID, PUT, POST, DELETE) including edge cases (empty body, duplicate ID, delete non-existent). These tests pin current behavior including any bugs.

**Extraction path:** New service (Spring Boot 3 / FastAPI) with clean domain model behind an API gateway. Monolith stays active. A contract test on the same commit proves both pass.

---

### 3. Database Profile Initializer — Risk: HIGH (do not extract)

`SpringApplicationContextInitializer` is not a candidate for extraction — it is a candidate for deletion. It exists solely to detect Cloud Foundry bound services at startup. In a containerized deployment, this logic is replaced by environment variables and standard Spring Boot externalized configuration.

**Decision:** Replace with 12-factor config (`SPRING_PROFILES_ACTIVE` env var) as part of the Album Catalog Service build. Do not touch this class until characterization tests are green.

---

## Anti-Corruption Layer

The `Album` entity from the monolith must not leak into the new Album Catalog Service's public API shape. Specifically:

- `@Entity`, `@GenericGenerator`, `@Column(length=40)` are JPA internals — must not appear in the new service's API contract
- The `albumId` field (distinct from `id`) must be evaluated before the new service adopts it — it may be a legacy artifact
- A contract test asserting that no monolith field annotation appears in the new service's OpenAPI spec is the enforcement mechanism (see The Fence, Challenge 6)

---

## What We Chose NOT To Do

**1. Not extracting Platform Info as a separate service.**  
`InfoController` is 30 lines of read-only CF metadata. Extracting it creates a deployable unit with zero business value and adds operational overhead. It stays in the monolith until the monolith is decommissioned.

**2. Not keeping ErrorController in any production service.**  
`/errors/kill`, `/errors/fill-heap`, `/errors/throw-exception` are chaos engineering test endpoints. They will be deleted from the codebase, not extracted. They have no business value and represent a security risk in production.

**3. Not rewriting the frontend.**  
AngularJS 1.x reached end-of-life in December 2021. Rewriting it is net-new product work, not modernization. We extract the existing SPA as-is into a container. A frontend rewrite is a separate track, separate ADR.

**4. Not changing the Album data model before the service boundary is stable.**  
The `albumId` field looks redundant, but modifying the schema before characterization tests exist removes the safety net. Schema cleanup happens after The Pin (Challenge 4) is green.

**5. Not doing a big-bang Spring Boot 2.4 → 3.x upgrade on the monolith.**  
Spring Boot 3 requires Java 17+ and has breaking changes in security, persistence, and actuator. Upgrading the monolith before extracting services conflates two separate risks. The new Album Catalog Service will be built on Spring Boot 3 from the start.

**6. Not using Cloud Foundry libraries in new services.**  
`cf-java-client`, `java-cfenv`, and CF manifest conventions are monolith baggage. New services use standard Spring Boot externalized config and Docker/Kubernetes deployment.

---

## Decision

Extract in this order:

```
Phase 1: Frontend SPA → nginx container
Phase 2: Album Catalog Service → new service behind API gateway (strangler fig)
Phase 3: Replace SpringApplicationContextInitializer with env-var config
Phase 4: Decommission monolith
```

Each phase requires:
- Characterization tests green before the phase starts
- Contract tests green on the same commit the phase lands
- Monolith continues to serve traffic until the new service is proven

---

## Consequences

- Monolith will exist alongside new services for a period — this is intentional
- Two test suites must be maintained in parallel during transition
- The API gateway adds one network hop — acceptable tradeoff for safe extraction
- Team must resist the urge to refactor the monolith's internals during extraction
