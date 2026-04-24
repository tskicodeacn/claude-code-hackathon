# Challenge 1 — The Stories

User stories for the Album Catalog capabilities that actually matter.
Acceptance criteria are written to be executable by a tester, not aspirational.
Stakeholder disagreements are captured explicitly — not smoothed over.

---

## US-01 — Browse the Album Catalog

**As a** music fan using the app,  
**I want to** see a list of all albums,  
**so that** I can discover what's in the catalog.

### Acceptance Criteria

- [ ] `GET /albums` returns HTTP 200
- [ ] Response is a JSON array (empty array `[]` when catalog is empty — not null, not 404)
- [ ] Each album in the list contains: `id`, `title`, `artist`, `releaseYear`, `genre`, `trackCount`, `albumId`
- [ ] `trackCount` defaults to `0` when not provided at creation time
- [ ] `albumId` is `null` when not provided at creation time
- [ ] Response contains no JPA annotation names, Java package names, or `_class` fields

### Stakeholder Disagreement — SD-01a: Empty catalog response shape

| Stakeholder | Position |
|-------------|----------|
| **Frontend (AngularJS)** | Needs `[]` — iterates with `ng-repeat`, null breaks the view |
| **Mobile team** | Also needs `[]` — same reason |
| **Current monolith** | Returns `[]` ✓ |
| **Decision** | `[]` is the contract. Non-negotiable. |

---

## US-02 — View a Single Album

**As a** music fan,  
**I want to** view the full details of a specific album,  
**so that** I can see its track count and metadata.

### Acceptance Criteria

- [ ] `GET /albums/{id}` returns HTTP 200 and the album JSON when the album exists
- [ ] Response contains all required fields: `id`, `title`, `artist`, `releaseYear`, `genre`, `trackCount`, `albumId`
- [ ] `GET /albums/{nonexistent-id}` returns HTTP **404** *(see SD-02a below)*
- [ ] `GET /albums/{deleted-id}` returns HTTP **404** after deletion *(same)*

### Stakeholder Disagreement — SD-02a: 404 vs 200+empty for missing albums

This is the most contested story. The monolith currently returns `HTTP 200 + empty body` for missing albums (`orElse(null)` bug). The new service returns 404.

| Stakeholder | Position |
|-------------|----------|
| **Product** | Fix it. 200+empty is not REST. A missing resource is 404. |
| **Ops / API consumers** | We have scripts that check `status == 200`. Changing this breaks them silently. |
| **Frontend** | Current AngularJS code doesn't check status — it checks if the body is empty. Either behavior works for the UI. |
| **QA** | The monolith characterization test *pins the bug* — it documents 200+empty as current behavior, so the delta is explicit and trackable. |
| **Decision** | New service returns **404**. Monolith retains 200+empty. The contract test documents the divergence. Consumers must be updated before cutover (see `cutover/runbook.md` Appendix). |

---

## US-03 — Add an Album

**As a** catalog administrator,  
**I want to** add a new album to the catalog,  
**so that** music fans can discover it.

### Acceptance Criteria

- [ ] `PUT /albums` with a valid JSON body returns HTTP 200 and the created album
- [ ] Response includes a server-generated `id` (UUID format)
- [ ] Client-supplied `id` in the request body is **ignored** — server always generates a new one
- [ ] `title` and `artist` are required — request without them returns HTTP 422
- [ ] Album immediately appears in `GET /albums` response after creation
- [ ] `trackCount` defaults to `0` if not supplied
- [ ] `albumId` is `null` if not supplied

### Stakeholder Disagreement — SD-03a: The `albumId` field

| Stakeholder | Position |
|-------------|----------|
| **Product** | What even is `albumId`? It's always null in the seed data. Drop it. |
| **Data team** | There may be downstream systems importing the JSON that depend on this field being present. Unknown. |
| **Arch** | Field is `null` in 100% of current responses — safe to carry forward as nullable. Dropping it is a schema break. |
| **Decision** | Carry `albumId` forward as a nullable optional field. Do not drop it until downstream consumers are audited. Tracked in backlog. |

### Stakeholder Disagreement — SD-03b: PUT vs POST for creation

| Stakeholder | Position |
|-------------|----------|
| **Product** | Should be `POST /albums` — that's standard REST for creation. |
| **Backend** | Monolith uses `PUT /albums` for create and `POST /albums` for update. Changing it breaks the existing frontend. |
| **Decision** | Preserve monolith convention (`PUT` = create, `POST` = update) for now. Renaming to REST-standard verbs is a separate story, post-extraction. |

---

## US-04 — Update an Album

**As a** catalog administrator,  
**I want to** edit an existing album's metadata,  
**so that** I can correct mistakes or add track count after release.

### Acceptance Criteria

- [ ] `POST /albums` with a body containing a valid `id` returns HTTP 200 and the updated album
- [ ] Updated fields are persisted — subsequent `GET /albums/{id}` reflects the changes
- [ ] `id` field in the response matches the `id` sent in the request (no re-generation)
- [ ] `POST /albums` with a non-existent `id` returns HTTP 404 *(contract fix — monolith behavior untested)*
- [ ] Partial updates are not supported — full album object must be sent

---

## US-05 — Delete an Album

**As a** catalog administrator,  
**I want to** remove an album from the catalog,  
**so that** unavailable or incorrect entries don't mislead users.

### Acceptance Criteria

- [ ] `DELETE /albums/{id}` returns HTTP 200 with **empty body** *(matches monolith)*
- [ ] Album no longer appears in `GET /albums` after deletion
- [ ] `GET /albums/{deleted-id}` returns HTTP **404** after deletion *(contract fix — see SD-02a)*
- [ ] `DELETE /albums/{nonexistent-id}` returns HTTP 200 silently *(idempotent — matches monolith)*

### Stakeholder Disagreement — SD-05a: Return 404 on delete of non-existent resource?

| Stakeholder | Position |
|-------------|----------|
| **Product** | Deleting something that doesn't exist should be 404. |
| **Backend** | Monolith swallows it silently (200). Idempotent deletes are operationally safer — retries don't fail. |
| **Decision** | Keep silent 200 for now (matches monolith, safer for retries). Document as known divergence from strict REST. |

---

## Backlog — Not In Scope for This Extraction

| Item | Reason deferred |
|------|-----------------|
| Album search / filter | Not in monolith — net-new feature, separate track |
| Pagination on `GET /albums` | Monolith returns all albums; no pagination exists to characterize |
| Authentication / authorization | Out of scope for this demo app |
| `POST /albums` → `POST` for create | Breaking change to frontend; post-extraction cleanup |
| Drop `albumId` field | Requires downstream consumer audit first (see SD-03a) |
| Frontend rewrite (React) | Separate ADR — not modernization, it's net-new product work |
| Multi-DB support in new service | New service uses a single backend (in-memory → swap for one real DB) |

### Stakeholder Disagreement — SD-BL-01: Multi-DB support

| Stakeholder | Position |
|-------------|----------|
| **Infra** | The whole point of Spring Music is demonstrating multi-DB. We should keep it. |
| **Arch** | The multi-DB switching was a Cloud Foundry demo artifact, not a business requirement. Pick one DB, reduce operational complexity. |
| **Product** | We have zero users who care which database stores their albums. |
| **Decision** | New service uses a single backend. The monolith retains multi-DB until decommissioned. The demo value stays in the monolith for now. |
