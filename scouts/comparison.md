# The Scouts — Agent vs Human Ranking Comparison

**Run date:** 2026-04-24  
**Method:** 5 independent subagents, one per seam, no shared context, parallel launch  
**Human baseline:** ADR-001 (`spring-music-master/docs/adr/001-decomposition-plan.md`)

---

## Agent-Generated Ranking (by composite risk score)

Composite = coupling + test_coverage + data_model_tangle + business_criticality (each 1–5)

| Rank | Seam | Composite | Risk | Recommendation | Key finding |
|------|------|-----------|------|----------------|-------------|
| 1 | error_endpoints | 8 | LOW | **DELETE** | Zero dependencies, chaos-only, production security risk |
| 2 | platform_info | 9 | LOW | EXTRACT | Pure POJO, read-only, no persistence, trivial criticality |
| 3 | frontend_spa | 10 | LOW | EXTRACT | Pure HTTP seam, zero server-side coupling |
| 4 | album_catalog | 16 | MEDIUM | EXTRACT | Max data-model tangle, max business criticality |
| 5 | db_profile_init | 17 | HIGH | **DEFER** | Pre-context lifecycle, zero tests, app-breaking if wrong |

---

## Human Ranking (ADR-001)

| Rank | Seam | Risk | Decision |
|------|------|------|----------|
| 1 (extract first) | frontend_spa | LOW | EXTRACT |
| 2 (extract second) | album_catalog | MEDIUM | EXTRACT |
| 3 (do not extract) | db_profile_init | HIGH | REPLACE with env config |
| — | platform_info | — | STAY (not worth extracting) |
| — | error_endpoints | — | DELETE |

---

## Where They Agree

**db_profile_init — highest extraction risk (both agree)**  
Both rank it last. Agents score coupling=5 and business_criticality=5 (full app fails to start). Human ADR says "do not touch unless explicitly instructed." Perfect agreement on the most dangerous seam.

**error_endpoints — delete, not extract (both agree)**  
Agent recommends DELETE unprompted after reading the source (`System.exit`, OOM loop, no business logic). ADR-001 also schedules it for deletion. The agents caught the security risk independently.

**album_catalog — medium risk, worth extracting (both agree)**  
Agents score data_model_tangle=5 (max) and business_criticality=5, landing on MEDIUM overall. ADR-001 calls it medium risk and the second extraction target. Agreement on both risk level and recommendation.

---

## Where They Differ

### platform_info: EXTRACT vs STAY

**Agents say:** LOW risk (coupling=2, data_model_tangle=1), recommend EXTRACT.  
**ADR-001 says:** Don't extract. "Extracting creates a deployable unit with zero business value and adds operational overhead."

**Why the gap:** Agents scored technical extraction risk correctly — the module is clean and isolated. But they missed the ROI calculation. Low technical risk ≠ "worth doing." ADR-001's decision was driven by operational cost (a new deployable unit) vs business value (zero), not by technical coupling. The agents had no way to reason about ops overhead without being explicitly prompted.

**Lesson:** Technical risk scores need a separate "extraction ROI" dimension. A module can be trivially safe to extract and still not be worth extracting.

### frontend_spa: rank 3 (agents) vs rank 1 (human)

**Agents say:** rank 1 tied with platform_info and error_endpoints, composite score 10.  
**ADR-001 says:** Extract first — lowest risk, pure operational move.

**Why the gap:** Agents gave frontend_spa a business_criticality=3 (moderate, user-facing) which pushed its composite score slightly above platform_info and error_endpoints. ADR-001 prioritizes it first precisely because it IS user-facing but has zero technical coupling — the extraction is purely operational (nginx container), making it the lowest-friction first step. The agents correctly identified the low risk but didn't weigh "frictionless first win" as a prioritization criterion.

---

## Summary

| Dimension | Agreement |
|-----------|-----------|
| Most dangerous seam (db_profile_init) | Full agreement |
| Modules to delete (error_endpoints) | Full agreement |
| Core domain is worth extracting (album_catalog) | Full agreement |
| platform_info: extract or stay? | **Diverged** — agents say EXTRACT, human says STAY |
| Extraction order (frontend first) | **Diverged** — agents tied frontend with others, human prioritizes it |

**Overall:** Agents and human agree on 3/5 seams completely. The two divergences share a root cause: agents score technical risk well but miss **operational cost** (new deployable unit overhead) and **strategic sequencing** (lowest-friction win first). Both of these are judgment calls that require context beyond the source code.

A prompt addition like "also score: operational overhead of running a new service (1=trivial, 5=significant)" and "prefer the smallest safe first extraction" would likely close both gaps.
