# AGENTS-backend.md

Kotlin/JVM-backendkonvensjoner for `tiltakspenger`. Les [`AGENTS.md`](AGENTS.md) først for de globale reglene.

> Gjelder alle Kotlin-backendtjenester og (i hovedsak) `tiltakspenger-libs`. Libs har ekstra arkitekturkonvensjoner dokumentert i [`tiltakspenger-libs/AGENTS.md`](tiltakspenger-libs/AGENTS.md).

## Arkitektur

- **Arkitekturretning — to lag:** Målbildet er **to lag** per feature/domeneområde, `domene/` og `infra/`, der service-/orkestreringslogikk bor i domenet. Vi er på vei dit, men omskrivingen er gradvis og kan ta år — derfor finnes begge formene i kodebasen samtidig. **Ikke gjør en stor migrering på eget initiativ; følg strukturen som allerede finnes i repoet/feature-området du jobber i.** For ny kode, foretrekk målbildet der det er naturlig.
  - `domene/` — ren domenelogikk, ingen eksterne avhengigheter. Skal ikke importere fra `*.infra.*`. I målbildet bor også services her: tilstandsbærende orkestrering mellom domene og infrastruktur, med minimalt/ingen forretningslogikk.
  - `infra/` — infrastruktur: setup, routes, repos, kafka consumers/producers, klienter (http), DTO-er og DTO-mapping.
  - `service/` *(eldre form, under utfasing)* — et orkestreringslag skilt ut fra domenet «fra gammelt av». Flere repoer har fortsatt dette. Når du jobber i et slikt repo, behold den lokale strukturen i stedet for å flytte alt på én gang.
- **Pakkerot**: `no.nav.tiltakspenger.<modul>`
- **DDD**: domenelogikk hører hjemme på domenemodellen som er nærmest dataene; `init`/`require`-blokker håndhever invarianter.

## Språk og stil

- Kotlin JVM på gjeldende LTS; nyeste stabile Kotlin, eksperimentelle features er tillatt
- 4 mellomrom som innrykk, trailing comma både i deklarasjoner og kallsteder
- **Ingen star imports** — alltid eksplisitt
- **KDoc og kommentarer: én setning per linje.** Skriv hver setning i KDoc (`/** ... */`) og vanlige kommentarer på sin egen linje, med linjeskift etter hvert punktum, i stedet for å pakke flere setninger sammen i én lang avsnittslinje. Dette gir renere diffs (én endret setning = én endret linje) og bedre lesbarhet. Gjelder også `//`-kommentarer som består av flere setninger. (Agenter glipper ofte på dette — sjekk før du er ferdig.)
- **Norske domenenavn** — se språkregelen i [`AGENTS.md`](AGENTS.md#delte-konvensjoner). Domenetyper, pakker, funksjoner og felter som modellerer forretningsbegreper bruker norsk (`Sak`, `Søknad`, `Periode`, `Behandling`, `Vedtak`, `Saksbehandler`, …). Ikke oversett til engelsk.
- Funksjonell stil og immutabilitet foretrekkes — unngå `var` og muterbar tilstand
- Ingen `Optional` eller Arrows `Option` — bruk nullable typer eller `Either`
- **Aldri baser logikken vår på Kotlins `Result`.** Vi modellerer forventede feil med `Either` (se Feilhåndtering). `Result` skal **ikke** brukes som retur-/flyttype — og helt spesielt ikke returneres innover i domenet. Hvis du møter `Result` i ny kode, skriv det om til `Either` (eller nullable der det passer). Helt unntaksvis kan tredjeparts-API-er tvinge oss til å forholde oss til `Result`; håndtér det da på grensen og oversett umiddelbart til `Either`.

## Feilhåndtering

- Bruk **Arrows `Either<ErrorType, SuccessType>`** for forventede feil som kalleren skal håndtere (validering, brudd på forretningsregler).
- Feiltyper er sealed interfaces med beskrivende data objects/classes.
- **Ikke kast exceptions selv** fra domene-/applikasjonskode — modellér feilen som `Either`. Vi aksepterer at tredjepartsbiblioteker (JDBC, HTTP-klienter, Kafka, …) kaster; fang dem på grensen med `Either.catch { ... }.mapLeft { ... }` og oversett til en domene-/route-feil. Det betyr i praksis **ingen `try`/`catch` eller `runCatching` i ny kode**.
- **HTTP-klienter skal ikke kaste exceptions for feiltilfeller — de skal returnere `Either`.** Bruk den felles `HttpKlient` fra `tiltakspenger-libs:httpklient`, og la porten/interfacet returnere `Either<HttpKlientError, T>` (eventuelt en domenespesifikk feiltype som wrapper `HttpKlientError`, jf. `TilgangskontrollFeil`). Kallende service/jobb håndterer `Either` eksplisitt og logger feil **én gang** via delt `HttpKlientError.loggFeil(...)`. Møter du en gammel throw-basert klient, migrér den til `Either`-kontrakten (ikke behold throw-kontrakten). Sporing av migreringen: epic [navikt/tiltakspenger#15](https://github.com/navikt/tiltakspenger/issues/15).
- **Unntak — `PostgresRepo`:** repo-implementasjonene lar i praksis exceptions boble opp i stedet for å returnere `Either`. Følg den eksisterende konvensjonen for repos med mindre det er en god grunn til å avvike.
- **Unntak — autorisasjon i interne API-er:** for endepunkter som kun konsumeres av våre egne frontender skal vi alltid verifisere at IDer i request faktisk tilhører personen/saken brukeren har tilgang til, men det er greit å kaste en exception (typisk håndtert som 403/404 av et felles `StatusPages`-oppsett) i stedet for å modellere det som en `Either.Left`. Kost/nytte: frontenden vi eier sender normalt gyldige IDer, så dette er en defense-in-depth-sjekk og ikke en forventet feilflyt.
- **Unntak — Texas (`tiltakspenger-libs:texas`):** `TexasHttpClient` logger og re-kaster exceptions ved feil i token-introspeksjon og henting av system-tokens. Konsumenter trenger normalt ikke å fange disse — la dem boble opp og bli håndtert som 401/500 av Ktor-pipelinen / `StatusPages`. `requireXxxPrincipal()`-hjelperne i `texas` kaster `IllegalStateException` hvis principal mangler; dette er en programmeringsfeil og skal ikke catches.
- **Skjerpet krav — eksponerte API-er (`tiltakspenger-datadeling` m.fl.):** API-er som konsumeres av andre fagsystemer utenfor teamet skal ha eksplisitt, modellert feilhåndtering hele veien ut til route-laget med `Either`, og oversette til veldokumenterte HTTP-feil. Ikke la generiske exceptions lekke ut som 500 her — konsumentene er avhengige av en stabil og tydelig feilkontrakt. Dette overstyrer Texas-/repo-unntakene over for selve route-laget i datadeling.
- I tester: bruk `getOrFail()` fra `tiltakspenger-libs:test-common` for å pakke ut `Either`.

## Typede ID-er

- Privat konstruktør, delegerer til `UlidBase`, prefikset string-representasjon
- Factory-metoder: `random()`, `fromString()`, `fromUUID()`
- `init`/`require`-blokker for invarianter
- Kanoniske eksempler i `tiltakspenger-libs:common`

## Clock og tid

- Bruk `java.time.Clock` — kall aldri `Instant.now()` / `LocalDateTime.now()` / `LocalDate.now()` uten en `Clock`-parameter
- Bruk `no.nav.tiltakspenger.libs.common.nå(clock)` i stedet for `LocalDateTime.now(clock)`
- Produksjonskode tar imot `Clock` som konstruktør-/funksjonsparameter
- I tester: bruk `fixedClock` eller `TikkendeKlokke` fra `tiltakspenger-libs:test-common`

## Database

- **PostgreSQL** med **Flyway**-migrasjoner
- Flerlinjet SQL med `"""`-strenger, ren tekst (ingen templating)
- Formatér SQL som om den lå i en `.sql`-fil: store bokstaver på keywords, riktig innrykk
- **Skriv SQL-en inline i funksjonen som bruker den** — ikke trekk den ut til en top-level konstant. Vi ønsker ikke å være DRY her.
- Repositories: interface ender på `Repo`, Postgres-implementasjon på `PostgresRepo` (`SøknadRepo` / `SøknadPostgresRepo`)
- Lag fakes for alle repos, både til testing og til lokal kjøring

## JSON

- Bruk den delte `objectMapper` fra `tiltakspenger-libs:json` og hjelperne `serialize()`/`deserialize()`
- **Ikke** lag egne `ObjectMapper`-instanser

## Logging

- Bruk `Sikkerlogg` fra `tiltakspenger-libs:logging` for sensitive data / personopplysninger
- Standardlogging bruker `kotlin-logging` (`io.github.oshai`)
- Overstyr `toString()` på typer som inneholder sensitive data for å unngå utilsiktede lekkasjer

## Testing

- **Kotest** for assertions: `shouldBe`, `shouldThrowWithMessage`. For større/komplekse objektsammenligninger: foretrekk `shouldBeEqualToIgnoringLocalDateTime` fremfor `shouldBe`. For JSON-assertions: foretrekk `shouldEqualJsonIgnoringTimestamps` fremfor `shouldEqualJson`.
- **JUnit 5** som test-runner (JUnit 4 er ekskludert globalt)
- **Mockk** er tilgjengelig, men vi foretrekker generelt fakes fremfor mocks
- **Testcontainers** for integrasjonstester mot ekte DB / Kafka
- Testlivssyklus: `@TestInstance(Lifecycle.PER_CLASS)`
- **Ikke** bruk JUnits assertion-metoder (`assertEquals`, `assertTrue`, …)

### Ende-til-ende og databasetester

- **Foretrekk ende-til-ende route-tester mot ekte DB.** Send JSON inn på route-laget, assert på JSON-responsen, og suppler ved å spørre databasen og inspisere fakes for sideeffekter når responsen ikke dekker alt.
- **To kjøremoduser for DB-tester (testcontainers, via `TestDatabaseManager` i `tiltakspenger-libs:persistering-test-common`):**
  - **Ikke-isolert (standard, parallelt skjema):** tester deler skjema og lever side om side. Gi hver test sin egen sak/person (unike `sakId`/`saksnummer`/`fnr`) slik at de ikke kolliderer.
  - **Isolert:** tømmer DB før testen og kjører sekvensielt. Reserver dette for **aggregerte / på-tvers-av-sak**-tester — typisk jobber som spør på tvers av alle saker. Isolert modus er treg; ikke bruk den når en sak-scoped test holder.
- **Deterministiske, sekvensielle id-generatorer i tester.** Bruk delte generatorer for `saksnummer`, `fnr` og `journalpostId` (sekvensielle og trådsikre) i stedet for tilfeldige verdier som `Fnr.random()`. Tilfeldige 11-sifrede fnr kolliderer sjelden i én kjøring, men i et delt test-skjema gir bursdagsparadokset reell flaky-risiko over mange CI-kjøringer. Generatorene holdes på **ett høyt nivå** (én delt instans i test-db-manageren, jf. `idGeneratorsFactory`) og injiseres ned i test-konteksten — **ikke** legg prosessglobal tilstand dypt inne i selve generatoren.

## Bygg, lint og statisk analyse

Alle Kotlin-backendtjenester deler den samme baseline-byggkonfigurasjonen.

- **Spotless** + **ktlint** (`com.diffplug.spotless`) til formatering, med disse overstyringene:
  - `ktlint_standard_max-line-length` = off
  - `ktlint_standard_function-signature` = disabled
  - `ktlint_standard_function-expression-body` = disabled
  - `ktlint_code_style` = `ktlint_official`
  - `ktlint_experimental` = enabled
- **Detekt** for statisk analyse (`config/detekt.yml`); navnemønstrene tillater norske tegn (`æøå`)
- **Kover** (`org.jetbrains.kotlinx.kover`) for coverage der det er aktivert. `koverVerify` håndhever en streng linjedekningsterskel (i `tiltakspenger-libs` er kravet **100 %**), og kjøres som en del av `build`/CI. Den kjøres **ikke** av `:<modul>:test` alene, så det er lett å overse: kjør `./gradlew :<modul>:koverVerify` (eller full `build`) etter kodeendringer, og legg til tester for ny/endret kode. Unngå å skrive uoppnåelig defensiv kode (f.eks. `?: error(...)` på en gren som aldri kan nås) på egne linjer — kover teller dem som udekket og feiler bygget.
- **Gradle version catalog** i `gradle/libs.versions.toml` der den finnes
- **`com.github.ben-manes.versions`**-plugin for sjekk av oppdateringer på avhengigheter

Standard hjelpeskripter (ett sett per sub-repo):

```bash
./gradlew spotlessApply build        # lint + bygg + test
./gradlew :<modul>:test              # test én enkelt modul
./lint_and_build.sh                  # spotless + bygg + test
./clean_lint_and_build.sh            # clean (uten cache) + spotless + bygg + test
```

> `tiltakspenger-libs` er unntaket: det deployes ikke til NAIS og bruker en delt **convention-plugin** (`tiltakspenger-lib-conventions`) i stedet for å duplisere build-oppsettet i hver submodul. Se [`tiltakspenger-libs/AGENTS.md`](tiltakspenger-libs/AGENTS.md).

## Avhengigheter

- Minimér eksterne avhengigheter; bruk `testImplementation` / `compileOnly` der det er mulig
- Bruk version catalog der den finnes

## Auth og infra (backend-spesifikt)

- Autentisering via **NAIS Texas** (`tiltakspenger-libs:texas`) — token-introspeksjon og system-tokens
- Tjenester containeriseres med multi-stage Dockerfiles
- Kafka (Confluent) for hendelsesdrevet kommunikasjon
- PostgreSQL med Flyway for persistens
- Prometheus-metrikker via Micrometer (`io.micrometer:micrometer-registry-prometheus`)

