# AGENTS.md

> **Self-update rule:** When you make changes to project structure, conventions, dependencies, API patterns, or workflows described in this file, update this file to reflect those changes as part of the same commit.

## Overview

`tiltakspenger` is a NAV monorepo for the "tiltakspenger" (employment scheme benefits) system. It consists of multiple Kotlin/JVM backend services and TypeScript/React frontend applications, all managed as Gradle composite builds and individual npm projects.

## Repository Structure

| Module | Type | Description |
|---|---|---|
| `tiltakspenger-arena` | Kotlin backend | Arena integration |
| `tiltakspenger-datadeling` | Kotlin backend | Data sharing service |
| `tiltakspenger-iac` | IaC | Infrastructure as code |
| `tiltakspenger-journalposthendelser` | Kotlin backend | Journal post event handling |
| `tiltakspenger-libs` | Kotlin library | Shared library (see its own AGENTS.md) |
| `tiltakspenger-meldekort` | TypeScript frontend | Meldekort UI |
| `tiltakspenger-meldekort-api` | Kotlin backend | Meldekort API |
| `tiltakspenger-meldekort-microfrontend` | TypeScript frontend | Meldekort microfrontend |
| `tiltakspenger-pdfgen` | Templates | PDF generation templates |
| `tiltakspenger-saksbehandling` | TypeScript frontend | Case management UI (Next.js) |
| `tiltakspenger-saksbehandling-api` | Kotlin backend | Core case management API |
| `tiltakspenger-soknad` | TypeScript frontend | Citizen-facing søknad UI |
| `tiltakspenger-soknad-api` | Kotlin backend | Application/søknad API |
| `tiltakspenger-tiltak` | Kotlin backend | Tiltak integration |


---

## Kotlin Backend Conventions

### Architecture

- **Layered structure per feature/domain area:**
  - `domene/` — pure domain logic, no external dependencies
  - `infra/` — infrastructure: routes, repos, kafka consumers/producers, HTTP clients
  - `service/` — stateful services that orchestrate domain logic and infrastructure. Keep them thin and focused on orchestration, not business logic.
- **Package root**: `no.nav.tiltakspenger.<module>`

### Language & Style

- Kotlin JVM 21 (following LTS), Kotlin (newest stable, experimental features allowed)
- 4-space indentation, trailing commas (in both declarations and call sites)
- **No star imports** — always use explicit imports
- **Norwegian names** are used for domain concepts (e.g., `Sak`, `Søknad`, `Periode`, `Behandling`)
- Functional style, immutability preferred — avoid `var` and mutable state
- Domain logic belongs on the domain model closest to the data
- `init` blocks enforce domain invariants
- No `Optional` or Arrow's `Option` — use nullable types or `Either`

### Error Handling

- Use **Arrow's `Either<ErrorType, SuccessType>`** instead of throwing exceptions for cases where failure is expected and should be handled by the caller (e.g., validation errors, business rule violations). Database errors, network errors, and other truly exceptional cases can still throw exceptions.
- Error types are sealed interfaces with descriptive data objects/classes
- In tests, use `getOrFail()` from `tiltakspenger-libs:test-common` to unwrap `Either`

### Typed IDs

- Private constructor, delegated to `UlidBase`, prefixed string representation
- Factory methods: `random()`, `fromString()`, `fromUUID()`
- Use `init`/`require` blocks for invariants
- See `tiltakspenger-libs:common` for canonical patterns

### Clocks & Time

- Use `java.time.Clock` — never call `Instant.now()` without a `Clock` parameter
- use no.nav.tiltakspenger.libs.common.nå(clock) function instead of LocalDateTime.now(clock)
- Use `Instant.now(clock)`, `nå(clock)` and `LocalDate(clock)` in production code; accept `Clock` as a constructor/function parameter
- In tests, use `fixedClock` or `TikkendeKlokke` from `tiltakspenger-libs:test-common`


### Database
- Use **PostgreSQL** with **Flyway** for migrations
- Use multiline SQL strings with `"""` for readability.
- Plain strings without functions/templating.
- The SQL should be formatted as if it were in a `.sql` file, with keywords capitalized and proper indentation.
- Inline the SQL in the respective function. Never move it to it's own variable outside the function. We don't want to be DRY here.
- All repositories end with PostgresRepo and it's respective interface ends with Repo. For example `SøknadRepo` and `SøknadPostgresRepo`.
- We create fakes for all repos for testing and clients for testing and running locally.
### JSON

- Use the shared `objectMapper` from `tiltakspenger-libs:json` and its `serialize()`/`deserialize()` helpers
- Do **not** create custom `ObjectMapper` instances

### Logging

- Use `Sikkerlogg` from `tiltakspenger-libs:logging` for sensitive/personal data
- Standard logging uses `kotlin-logging` (`io.github.oshai`)

### Testing

- **Kotest** for assertions: `shouldBe`, `shouldThrowWithMessage` etc. For larger complex chain tests, prefer shouldBeEqualToIgnoringLocalDateTime over shouldBe.  When assering json strings, prefer shouldEqualJsonIgnoringTimestamps over shouldEqualJson.
- **JUnit 5** as test runner (JUnit 4 excluded globally)
- **Mockk** for mocking. Generally we use Fakes instead of mocks, but Mockk is available when needed.
- **Testcontainers** for integration tests against real databases/Kafka
- Test lifecycle: `@TestInstance(Lifecycle.PER_CLASS)`
- Do **not** use JUnit assertion methods (`assertEquals`, `assertTrue`, etc.)

### Build & Lint

```bash
./gradlew spotlessApply build        # lint + build + test
./gradlew :<module>:test             # test single module
./lint_and_build.sh                  # runs spotless, build, and test for all modules (defined in each sub-repo)
./clean_lint_and_build.sh            # cleans without cache, runs spotless, build, and test for all modules (defined in each sub-repo)
```

- **Spotless + ktlint** for formatting (configured per module via `com.diffplug.spotless`)
- **Detekt** for static analysis (config in `config/detekt.yml`)
- Naming patterns support Norwegian characters (æøå) — see `config/detekt.yml`
- `ktlint_standard_function-signature` and `ktlint_standard_function-expression-body` are disabled

### Dependencies

- Minimize external dependencies; scope test/compile-only where possible
- Version catalog in `gradle/libs.versions.toml` where present
- Use `com.github.ben-manes.versions` plugin to check for outdated dependencies

---

## TypeScript Frontend Conventions

### Frameworks & Libraries

- **React** with **TypeScript** (strict mode)
- **Next.js** for case management UI (`tiltakspenger-saksbehandling`)
- **Vite** or **Next.js** depending on the app
- **@navikt/ds-react** (NAV Aksel design system) for UI components — always prefer Aksel components over custom ones
- **@navikt/aksel-icons** for icons
- **react-hook-form** in some cases for form handling (we prefer to use a library for this if we can avoid it)
- **SWR** for data fetching
- **dayjs** for date handling

### Style & Formatting

- **Prettier** for formatting: 4-space `tabWidth`, `singleQuote: true`, `printWidth: 100`
- **ESLint** with TypeScript and React plugins
- Lint + format before committing (husky + lint-staged where configured)

```bash
npm run lint        # lint
npm run format      # prettier format
npm run build       # build
npm test            # run tests
```

### TypeScript

- **Strict mode enabled** (`"strict": true` in tsconfig)
- `noEmit: true` — TypeScript is used for type checking only, not compilation
- `moduleResolution: "bundler"`, `isolatedModules: true`
- Path aliases: `~/*` → `src/*` (Next.js apps), `@*` → `src/*` (Vite apps)
- Do **not** use `any` unless absolutely necessary (`@typescript-eslint/no-explicit-any` is off but avoid it)
- Unused vars are errors — prefix intentionally unused args with `_`

### ESLint Rules

- `react/react-in-jsx-scope`: off (React 17+ JSX transform)
- `@typescript-eslint/ban-ts-comment`: off
- `@typescript-eslint/no-unused-vars`: error (args matching `^(_|req|res|next)$` ignored)
- `no-undef`: off (TypeScript handles this)

### Structure

```
src/
  components/    # React components
  pages/         # Next.js pages (or routes/ for Vite)
  api/           # API fetch helpers
  types/         # TypeScript type definitions
  context/       # React context providers
  utils/         # Utility functions
  styles/        # CSS/styling
  auth/          # Auth helpers
```

### Testing

- **Jest** with `jest-environment-jsdom`
- **@testing-library/dom** and **@testing-library/jest-dom** for component tests

---

## Authentication & Security (NAIS)

- Authentication via **NAIS Texas** (`tiltakspenger-libs:texas`) — token introspection and system tokens
- **@navikt/oasis** on the frontend for token handling
- Never log personal data without using `Sikkerlogg`, override toString methods to avoid accidentally logging sensitive info.
- All services run on NAIS; follow NAIS conventions for config and secrets

## Infrastructure

- Services are containerized with Docker (multi-stage Dockerfiles)
- `docker-compose.yml` at root for local development
- Kafka (Confluent) for event-driven communication between services
- PostgreSQL for persistence (Flyway for migrations)
- Prometheus metrics via Micrometer (`io.micrometer:micrometer-registry-prometheus`)
