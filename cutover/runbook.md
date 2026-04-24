# Cutover Runbook: Album Catalog Service

**Service being cut over:** `/albums` endpoints  
**From:** Spring Music monolith (`spring-music-master/`)  
**To:** Album Catalog Service (`album-catalog-service/`)  
**Pattern:** Strangler Fig — monolith stays alive; traffic shifts endpoint by endpoint  

Rehearse this runbook at least once on a non-prod environment before the real cutover.  
Run `cutover/rehearse.bat` to execute the automated rehearsal steps.

---

## Roles

| Role | Responsibility |
|------|---------------|
| **Operator** | Executes this runbook step-by-step |
| **Observer** | Watches dashboards, calls ABORT if thresholds crossed |
| **Approver** | Gives GO/NO-GO at each gate |

---

## T-1h: Pre-Cutover Checklist

Run through this checklist one hour before the window opens.  
**All boxes must be checked before proceeding.**

- [ ] `run-tests.bat` exits 0 — both suites green (characterization + contract)
- [ ] `scorecard/run_scorecard.bat --dry-run --skip-behavior` exits 0
- [ ] Album Catalog Service starts cleanly: `uvicorn main:app --port 8080`
- [ ] Health check passes: `curl http://localhost:8080/openapi.json` returns 200
- [ ] Rollback procedure has been rehearsed (run `cutover/rehearse.bat` at least once)
- [ ] Team is online and reachable
- [ ] Incident channel open: post "cutover starting at [TIME]"
- [ ] Current monolith traffic baseline captured (req/s, error rate, p99 latency)

---

## Cutover Steps

### STEP 1 — Final pre-cutover validation (5 min)

```
run-tests.bat
```

Expected: `ALL GREEN — The Cut is verified.`  
**GATE:** Both suites green → proceed. Any failure → ABORT.

---

### STEP 2 — Start Album Catalog Service (2 min)

```
cd album-catalog-service
uvicorn main:app --host 0.0.0.0 --port 8080 --workers 2
```

Expected: `Application startup complete.`  
**GATE:** Service starts, health check returns 200 → proceed. Any error → ABORT.

```
# Health check
curl -s http://localhost:8080/openapi.json | python -m json.tool > /dev/null && echo OK
```

---

### STEP 3 — Smoke test (3 min)

Run the automated smoke tests against the live service:

```
cd album-catalog-service
python -m pytest tests/test_contract.py -v --tb=short -x \
  -k "put_album_returns_200 or list_albums_returns_200 or get_album_by_id_returns_404"
```

Expected: All three smoke tests pass.  
**GATE:** All pass → proceed. Any failure → ABORT.

---

### STEP 4 — Route traffic (2 min)

Update your API gateway / reverse proxy to forward `/albums/*` to Album Catalog Service.

**nginx example:**
```nginx
location /albums {
    proxy_pass http://album-catalog-service:8080;
}
```

**CF route services / Kubernetes ingress:** update the routing rule and confirm the change
is active before proceeding.

**GATE:** `curl -s http://gateway/albums` returns `[]` (empty list, 200) → proceed.

---

### STEP 5 — Monitor (10 min)

Watch for 10 minutes before declaring success. Observer watches:

| Signal | Threshold | Action |
|--------|-----------|--------|
| HTTP 5xx rate | > 1% | ROLLBACK |
| p99 latency | > 2× baseline | ROLLBACK |
| Contract test failures | any | ROLLBACK |
| `/albums` returns wrong shape | any | ROLLBACK |
| On-call discretion | — | ROLLBACK |

```
# Continuous smoke during monitoring window
watch -n 10 'curl -s http://gateway/albums | python -m json.tool | head -5'
```

---

### STEP 6 — Declare success

- [ ] 10 min window passed with no rollback triggers
- [ ] Incident channel: post "cutover complete — Album Catalog Service live"
- [ ] Update `CLAUDE.md` challenge tracker if this is Phase 2 of the extraction plan

---

## Rollback Procedure

**Trigger rollback as soon as any threshold is crossed — do not wait.**

### ROLLBACK STEP 1 — Revert routing (2 min)

Revert the API gateway config from STEP 4 to point back to the monolith.

```nginx
location /albums {
    proxy_pass http://spring-music-monolith:8888;
}
```

Confirm: `curl -s http://gateway/albums` returns a response from the monolith.

### ROLLBACK STEP 2 — Stop Album Catalog Service

```
# Find and stop the uvicorn process
pkill -f "uvicorn main:app"
```

### ROLLBACK STEP 3 — Verify monolith healthy

```
run-tests.bat
```

Expected: characterization suite green (monolith behavior unchanged).

### ROLLBACK STEP 4 — Incident report

- Document in incident channel: what triggered rollback, which step failed
- File a bug before retrying the cutover

---

## Decision Tree

```
Pre-cutover checklist all green?
    NO  → Fix issues, reschedule. Do not proceed.
    YES ↓

run-tests.bat green (STEP 1)?
    NO  → ABORT. Fix failing tests before cutover.
    YES ↓

Service starts and health check passes (STEP 2)?
    NO  → ABORT. Investigate startup errors.
    YES ↓

Smoke tests pass (STEP 3)?
    NO  → ABORT. Do not route traffic.
    YES ↓

Traffic routed, /albums returns 200 (STEP 4)?
    NO  → ROLLBACK immediately.
    YES ↓

10-minute monitoring window: any rollback trigger?
    YES → ROLLBACK immediately.
    NO  ↓

CUTOVER COMPLETE — declare success.
```

---

## Appendix: Port Reference

| Service | Port |
|---------|------|
| Spring Music monolith | 8888 (default Spring Boot) |
| Album Catalog Service | 8080 |
| Rehearsal instance | 8765 (rehearse.py uses this) |

## Appendix: Contract Differences (Known)

The new service intentionally diverges from the monolith in two cases:

| Endpoint | Monolith | New Service | Reason |
|----------|----------|-------------|--------|
| `GET /albums/{nonexistent}` | 200 + empty body | **404** | Bug fix |
| `GET /albums/{deleted}` | 200 + empty body | **404** | Bug fix |

Consumers that relied on the 200+empty behavior must be updated before cutover.
The characterization tests in `AlbumControllerCharacterizationTest.java` pin these bugs
on the monolith side so the delta is explicit and trackable.
