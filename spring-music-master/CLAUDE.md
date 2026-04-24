# Spring Music — Legacy Monolith

## What This Is

Spring Boot 2.4.0 monolith. Multi-database demo app for Cloud Foundry. One domain entity (`Album`), one REST controller, three repository implementations (JPA/MongoDB/Redis), and an AngularJS 1.2.16 SPA.

**This is the monolith being decomposed. Handle with care.**

## Critical Rules

1. **Do not modify any source file before characterization tests exist and pass.**  
   The Pin (Challenge 4) must be completed first.

2. **Do not touch `SpringApplicationContextInitializer`** unless explicitly instructed.  
   It is CF-specific startup wiring. A bug here breaks the entire application at boot.

3. **Do not add features to this codebase.**  
   All new functionality goes in `album-catalog-service/`. The monolith is in maintenance mode.

4. **Do not promote `Album` domain model fields to the new service's API.**  
   `@Entity`, `@GenericGenerator`, `@Column` are JPA internals — not public contract.  
   The `albumId` field (separate from `id`) has unclear semantics — do not copy blindly.

## Architecture Notes

- Active persistence backend is controlled by Spring profile: `jpa` (default/H2), `mysql`, `postgres`, `mongodb`, `redis`
- Profile auto-detection from CF services happens in `SpringApplicationContextInitializer`
- Local development uses H2 in-memory (no profile needed): `./gradlew bootRun`
- Data seed loaded from `src/main/resources/albums.json` on `ApplicationReadyEvent`

## Key Files

| File | Role |
|------|------|
| `web/AlbumController.java` | REST CRUD — the seam we're extracting |
| `domain/Album.java` | Domain entity — JPA annotations tangle persistence into domain |
| `repositories/jpa/JpaAlbumRepository.java` | Default (H2/relational) repository |
| `config/SpringApplicationContextInitializer.java` | CF profile wiring — HIGH RISK, do not touch |
| `web/ErrorController.java` | Chaos endpoints — scheduled for deletion |

## What Is Safe to Edit

- `src/test/` — add characterization tests freely
- `docs/` — add documentation freely
- `src/main/resources/application.yml` — configuration changes are low risk

## Build & Run

```bash
# Build
./gradlew clean assemble

# Run locally (H2 in-memory, no profile needed)
java -jar build/libs/spring-music.jar

# Run with specific DB profile
java -jar -Dspring.profiles.active=postgres build/libs/spring-music.jar
```
