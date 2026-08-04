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
- **`*Ex.kt`-filer er en del av domenetypen, ikke et lag utenfor den.** Extension-funksjoner på en domenetype samlet i egen fil (`RammebehandlingGjenopptaEx.kt`, `RammebehandlingLeggTilbakeEx.kt`, …) er bare filorganisering for å holde hovedfila lesbar. De regnes som typens egne metoder, og samme regler gjelder der: de skal håndheve invariantene og oppdatere typens metadatafelter. En operasjon som muterer domenetypen hører hjemme på typen — enten i hovedfila eller i en slik `*Ex.kt` — ikke i en service.
- **Bare typen selv skal kalle `copy()` på seg selv.** `copy()` omgår all validering i navngitte operasjoner og lar en kaller sette et felt uten å oppdatere de andre som hører sammen med det — typisk metadata som `sistEndret`, eller et resultat som må følge saksopplysningene. Kaller du `copy()` utenfra, har du laget en muterende operasjon på feil sted; lag i stedet en navngitt funksjon på typen (eller i dens `*Ex.kt`) som håndhever invariantene. Kotlin kan i prinsippet håndheve dette med privat konstruktør og `@ConsistentCopyVisibility`, men det er tungvint nok til at vi holder det som en konvensjon inntil videre.

## Språk og stil

- Kotlin JVM på gjeldende LTS; nyeste stabile Kotlin, eksperimentelle features er tillatt
- 4 mellomrom som innrykk, trailing comma både i deklarasjoner og kallsteder
- **Ingen star imports** — alltid eksplisitt
- **KDoc og kommentarer: én setning per linje.** Skriv hver setning i KDoc (`/** ... */`) og vanlige kommentarer på sin egen linje, med linjeskift etter hvert punktum, i stedet for å pakke flere setninger sammen i én lang avsnittslinje. Dette gir renere diffs (én endret setning = én endret linje) og bedre lesbarhet. Gjelder også `//`-kommentarer som består av flere setninger. (Agenter glipper ofte på dette — sjekk før du er ferdig.)
- **Norske domenenavn** — se språkregelen i [`AGENTS.md`](AGENTS.md#delte-konvensjoner). Domenetyper, pakker, funksjoner og felter som modellerer forretningsbegreper bruker norsk (`Sak`, `Søknad`, `Periode`, `Behandling`, `Vedtak`, `Saksbehandler`, …). Ikke oversett til engelsk.
- Funksjonell stil og immutabilitet foretrekkes — unngå `var` og muterbar tilstand
- Ingen `Optional` eller Arrows `Option` — bruk nullable typer eller `Either`
- **Aldri baser logikken vår på Kotlins `Result`.** Vi modellerer forventede feil med `Either` (se Feilhåndtering). `Result` skal **ikke** brukes som retur-/flyttype — og helt spesielt ikke returneres innover i domenet. Hvis du møter `Result` i ny kode, skriv det om til `Either` (eller nullable der det passer). Helt unntaksvis kan tredjeparts-API-er tvinge oss til å forholde oss til `Result`; håndtér det da på grensen og oversett umiddelbart til `Either`.
- **Exhaustive `when` over sealed types og enums — unngå `else`.** List alle varianter eksplisitt (grupper gjerne grener med lik håndtering: `is A, is B -> …`), slik at en ny variant gir kompileringsfeil der den må håndteres i stedet for å forsvinne stille inn i en `else`-gren. `else` er kun greit når subjektet ikke er sealed/enum, eller når en gren genuint har «alle andre»-semantikk over en stabil enum (f.eks. ukedager).
- **Bakgrunnsjobber navngis `*Jobb`, ikke `*Service`.** Klasser som kjøres av jobb-planleggeren (`Jobber.kt` / tilsvarende) heter `NoeJobb`; `*Service` er forbeholdt tjenester som kalles fra routes eller andre services.

## Feilhåndtering

- Bruk **Arrows `Either<ErrorType, SuccessType>`** for forventede feil som kalleren skal håndtere (validering, brudd på forretningsregler).
- Feiltyper er sealed interfaces med beskrivende data objects/classes.
- **Ikke kast exceptions selv** fra domene-/applikasjonskode — modellér feilen som `Either`. Vi aksepterer at tredjepartsbiblioteker (JDBC, HTTP-klienter, Kafka, …) kaster; fang dem på grensen med `Either.catch { ... }.mapLeft { ... }` og oversett til en domene-/route-feil. Det betyr i praksis **ingen `try`/`catch` eller `runCatching` i ny kode**.
- **HTTP-klienter skal ikke kaste exceptions for feiltilfeller — de skal returnere `Either`.** Se den egne seksjonen **HTTP-klienter** under for hele klientmønsteret.
- **Unntak — `PostgresRepo`:** repo-implementasjonene lar i praksis exceptions boble opp i stedet for å returnere `Either`. Følg den eksisterende konvensjonen for repos med mindre det er en god grunn til å avvike.
- **Unntak — autorisasjon i interne API-er:** for endepunkter som kun konsumeres av våre egne frontender skal vi alltid verifisere at IDer i request faktisk tilhører personen/saken brukeren har tilgang til, men det er greit å kaste en exception (typisk håndtert som 403/404 av et felles `StatusPages`-oppsett) i stedet for å modellere det som en `Either.Left`. Kost/nytte: frontenden vi eier sender normalt gyldige IDer, så dette er en defense-in-depth-sjekk og ikke en forventet feilflyt.
- **Unntak — Texas (`tiltakspenger-libs:texas`):** `TexasHttpClient` logger og re-kaster exceptions ved feil i token-introspeksjon og henting av system-tokens. Konsumenter trenger normalt ikke å fange disse — la dem boble opp og bli håndtert som 401/500 av Ktor-pipelinen / `StatusPages`. `requireXxxPrincipal()`-hjelperne i `texas` kaster `IllegalStateException` hvis principal mangler; dette er en programmeringsfeil og skal ikke catches.
- **Skjerpet krav — eksponerte API-er (`tiltakspenger-datadeling` m.fl.):** API-er som konsumeres av andre fagsystemer utenfor teamet skal ha eksplisitt, modellert feilhåndtering hele veien ut til route-laget med `Either`, og oversette til veldokumenterte HTTP-feil. Ikke la generiske exceptions lekke ut som 500 her — konsumentene er avhengige av en stabil og tydelig feilkontrakt. Dette overstyrer Texas-/repo-unntakene over for selve route-laget i datadeling.
- I tester: bruk `getOrFail()` fra `tiltakspenger-libs:test-common` for å pakke ut `Either`.

## HTTP-klienter

Alle utgående HTTP-kall gjøres med den felles `HttpKlient` fra `tiltakspenger-libs:httpklient` — den gir enhetlig timeout/retry/circuit breaker/logging/token-håndtering og `Either`-basert feilhåndtering. Ikke bruk ktor `HttpClient` eller `java.net.http` direkte i ny kode, og møter du en gammel håndrullet/throw-basert klient: migrér den til mønsteret under (kontrakten endres til `Either`, og skiftet rippler bevisst inn i kallende kode). `KabalHttpClient` i saksbehandling-api er kanonisk eksempel.

- **Kaster ikke — returnerer `Either`.** Porten/interfacet returnerer `Either<HttpKlientError, T>`, eventuelt en domenespesifikk feiltype som wrapper `HttpKlientError` (jf. `TilgangskontrollFeil`). Kallende service/jobb håndterer `Either` eksplisitt.
- **Domenefeil utleder fra `HttpKlientError` — ikke dupliser på kallstedet.** Når en domenefeiltype bærer en `HttpKlientError`, skal ikke kallstedet plukke ut `feil.rawResponseString`/`feil.metadata.statusCode` og sende dem inn som egne konstruktørargumenter ved siden av `feil` — det er dobbel data. Legg utledningen på feiltypen selv (sekundærkonstruktør/fabrikk som tar `(request, feil)`); `request` forblir derimot eksplisitt siden det er payloaden vi selv bygde. Se `KunneIkkeUtbetale` i saksbehandling-api som referanse.
- **Konstruktørmønster:** legg hele `HttpKlient(clock = clock) { ... }`-oppsettet som **default-verdi på `httpKlient`-parameteren** i konstruktøren, med `connectTimeout`/`defaultTimeout`/`successStatus`/`authTokenProvider` eksponert som egne parametre slik at tester kan overstyre (typisk med `HttpKlientFake`).
- **`AuthTokenProvider` injiseres som konstruktørparameter** — bygg `object : AuthTokenProvider` i `ApplicationContext`. Ikke wrap en `getToken`-lambda inne i klienten.
- **`Clock` inn i konstruktøren**, tres gjennom fra `ApplicationContext` (se Clock og tid).
- **DTO ≠ domene:** skill DTO fra domenemodellen; map DTO → domene i `.map { ... }` på responsen.
- **Ingen domenelogikk basert på HTTP-status.** Klient-metadata inn i domenet kun via en egen Metadata-fil for logging/notoritet; bruk `metadata.tidsstempler` (f.eks. `requestSendt`) for tidspunkter i stedet for `nå(clock)`.
- **Klienten logger ikke selv.** Feillogging skjer **én gang per feilsituasjon** i service/jobb via delt `HttpKlientError.loggFeil(logger, operasjon, kontekst)` (PII-fri `logger.error` + `Sikkerlogg.error` med rå request/respons).
- **Token-caching er løst — ikke bygg egen.** Texas cacher selv system- og OBO-tokens, og `httpklient` har `SkipCacheRetry` som ved behov tvinger fram et ferskt token. Ingen `invaliderCache()`-varianter i klienter.
- **PII i `toString()`:** data-klasser med PII (fnr/`brukerIdent`) overstyrer `toString()` og maskerer verdiene (`*****`).
- **KDoc-lenker på hver klient:** (a) kildekoden til API-et vi kaller (GitHub), (b) dokumentasjon (Confluence), (c) API-spec (Swagger/OpenAPI), (d) eierteamets Slack-kanal og (e) eierteamets oppføring i [Teamkatalogen](https://teamkatalogen.nav.no) — slik at rett kontaktpunkt er ett klikk unna når integrasjonen feiler.
- **Tester:** hver klient har en `*ClientTest` mot `HttpKlientFake`, inkludert én test som bygger default-`HttpKlient`-oppsettet. **Kover 100 % linjedekning** håndheves for klienter — legg FQN i `total.filters.includes.classes(...)` i repoets `build.gradle.kts`.

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
- **En domenetype skal aldri brukes til å lese fra eller skrive til databasen.** Hver app eier sine egne Db-typer og mapper til og fra dem (`TiltakstypeSomGirRettDb`, `TiltakDeltakerstatusDb` i saksbehandling-api er mønsteret). Eneste unntak er `java.time`-typer og liknende fra plattformen — aldri noe vi har laget selv, og **aldri en type fra `tiltakspenger-libs`**: da er libs i praksis skjemaet til en tabell i en annen app, og kan ikke endres uten migrering der. Det gjelder også felt inne i JSON-kolonner, som er lette å overse fordi de ikke er egne kolonner. Samme prinsipp gjelder ut mot API-er: en DTO skal ha sine egne verdier, ikke arve domenets `name`.

## JSON

- Bruk den delte `objectMapper` fra `tiltakspenger-libs:json` og hjelperne `serialize()`/`deserialize()`
- **Ikke** lag egne `ObjectMapper`-instanser

## Logging

- Bruk `Sikkerlogg` fra `tiltakspenger-libs:logging` for sensitive data / personopplysninger
- Standardlogging bruker `kotlin-logging` (`io.github.oshai`)
- **Logg aldri kun til sikkerlogg.** En sikkerlogg-innføring skal alltid ha en parallell linje i vanlig logg på samme nivå, med en nøytral (ikke-sensitiv) beskrivelse av hendelsen og en eksplisitt henvisning til sikkerlogg (f.eks. «Se sikkerlogg for detaljer»). Uten den finner ingen hendelsen i vanlig logg, og sporet til detaljene mangler.
- Overstyr `toString()` på typer som inneholder sensitive data for å unngå utilsiktede lekkasjer

### Logging av HTTP-kall

Regelen er **én debug/info-linje når kallet går bra, og én feillinje per feil — begge fra laget som har domenekonteksten.**

- **Klienten logger ikke.** Den vet hvilket endepunkt kallet gikk mot, men ikke hvilken sak, behandling eller saksbehandler det gjaldt, så linja blir uunngåelig generisk. Klienten mapper i stedet `HttpKlientError` til en domenefeil som **bærer feilen videre** (`KanIkkeHenteKontorhistorikk.KallFeilet(error)` er mønsteret), og servicen logger én gang med `HttpKlientError.loggFeil(logger, operasjon, kontekst)` / `HttpKlientResponse.loggSuksess(logger, melding)`.
- **Skriv aldri en dummy-exception for å få en stacktrace.** `RuntimeException("Trigger stacktrace for debug.")` var et forsøk på å bøte på at feil fra `java.net.http` oppstår asynkront på klientens I/O-tråd — men den ekte throwable-en havnet da bare i sikkerlogg, og dummy-stacktracen sier ingenting. Send den ekte feilen til `logger.error(throwable)`; den er PII-fri.
- **Stacktracen kan aldri fortelle hvor kallet gikk.** En `HttpConnectTimeoutException` lages på JDK-ens `SelectorManager`-tråd og har null applikasjonsframes. Alt som skal hjelpe deg i prod må stå i selve meldingen — det er derfor `loggFeil` skriver feilart, endepunkt, antall forsøk og varighet.
- **Ta stilling til `UriSynlighet` når du lager en klient.** Default er `KunSikkerlogg`, som gir `POST https://host/<skjult>` i vanlig logg. Har klienten faste stier uten personopplysninger i path eller query — identen ligger typisk i request-bodyen — sett `UriSynlighet.VanligLogg` i `HttpKlientConfig`, så navngir feilloggene endepunktet i klartekst.
- **Logg varigheten sammen med grensa.** `brukt: 1.003s` er ikke til å tolke alene — det kan være en klient som akkurat brøt 1 s, eller en som brukte en brøkdel av 30 s. `HttpKlientMetadata.tidsgrenser` bærer begge grensene, timeout-feil navngir den som brøt, og `loggSuksess` skriver `brukt: 4.8s av 5s per forsøk` som tidlig varsling.
- **Klassifiser ved grensa, ikke etterpå.** Når du oversetter en fremmed type (en JDK-exception, et wire-format) til vår egen, skal skillet avgjøres der og bæres videre. Utleder du det på nytt lenger ut i kjeden — spesialisert → generalisert → spesialisert — har mellomtypen kastet informasjon den fikk inn, og gjetningen kan divergere fra den opprinnelige klassifiseringen.

## Personopplysninger

Verdier som er personopplysninger markeres med **typen**, ikke med en kommentar eller en annotasjon: `Personopplysning` i `tiltakspenger-libs:common`, med kategorier under seg (`Stedsinformasjon`) og konkrete value classes (`Virksomhetsnavn`, `Tilknytningstittel`, `Fnr`).

- **Kompilatoren håndhever maskeringen.** Interfacet redeklarerer `toString()` som abstrakt, så enhver implementasjon *må* skrive sin egen. Man kan ikke glemme den.
- **Maskeringen arves.** En `data class` med en `Personopplysning`-property maskerer automatisk i sin genererte `toString()`. Klasser som inneholder slike felt skal derfor **ikke** ha håndskrevne `toString()`-overstyringer — la typen gjøre jobben.
- **Det ene hullet er `data class`,** som tilfredsstiller kompilatorkravet med sin genererte `toString()` og lekker alle feltene. Konsistregelen `PersonopplysningMaskererToString` krever at en `data class` som markerer seg deklarerer sin egen `toString()`.
- **Maskeringen gjelder kun `toString`.** Verdien hentes eksplisitt fra typens felt, slik at sikkerlogg, visning og lagring må be om den.
- **Hierarkiet er `sealed`** slik at settet av personopplysningstyper er opptellbart. Hver type har en `begrunnelse` som sier hva den utleverer om personen — grunnlaget for å avstemme mot personvernkonsekvensvurderingene (PVK). En ny personopplysningstype hører derfor hjemme i `common`, ikke lokalt i en app.
- **Husk stedsinformasjon.** Ikke bare fødselsnummer er sensitivt: for personer med adressebeskyttelse er *hvor de møter opp* ofte den mest sensitive opplysningen vi har. Arrangørnavn og sammensatte titler («Oppfølging hos Arrangør AS avd Strandveien») er adresser i praksis.

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

### Miljøflagg injiseres, slås aldri opp statisk

Målet er å kunne parallellisere tester i det uendelige.
Det forutsetter at ingen klasse endrer oppførsel basert på prosessglobal tilstand, for den tilstanden er felles for alle tester i samme JVM og kan ikke varieres per test.

- **`Configuration.isDev()` / `isProd()` / `isNais()` skal kun leses i komposisjonsroten** — `App.kt` og `ApplicationContext`/`*Context`-klassene der objektgrafen wires.
  Alt under dem tar flagget som en vanlig konstruktørparameter.
- **Aldri som defaultverdi i en klasse som deles mellom nais, test og lokalt.**
  `private val erDev: Boolean = Configuration.isDev()` er det verste tilfellet: oppslaget er usynlig på kallstedet, det skjer ved hver konstruksjon, og en test som ikke sender inn verdien arver stille miljøet til JVM-en den tilfeldigvis kjører i.
  Skriv `private val erDev: Boolean` uten default, så tvinges kallstedet til å ta stilling.
- **Mønsteret finnes allerede:** `SendMeldekortbehandlingTilBeslutterService(erProd: Boolean)` får flagget inn fra `MeldekortContext`, og `ApplicationContext(erDev = ...)` får sitt fra `App.kt`.
  En ren konstant som default (`erDev: Boolean = false`) er greit der det bare styrer loggnivå — det er ingen global tilstand, og defaulten skal da være den høylytte prod-oppførselen.

Samme resonnement gjelder all annen JVM-global tilstand: `System.setProperty`, statiske registre og `mockkStatic` hører ikke hjemme i testbar kode.

### Ingen defaults i prod for testenes skyld

**Prodsignaturer skal aldri ha en defaultverdi som bare finnes for at en test skal slippe å sende inn noe.**
Testene kan ha så mange buildere, hjelpefunksjoner og defaults de trenger for å være DRY — men den bekvemmeligheten skal ligge i testkoden, ikke klusse til produksjonskoden.

- Er argumentet obligatorisk for at prod skal oppføre seg riktig, er det obligatorisk i signaturen.
  «Femten testkallsteder bryr seg ikke» er et argument for en testhjelper, ikke for en default.
- Lag i stedet en tynn wrapper i `src/test`, med defaulten der.
  `konsumerTilbakekrevingshendelse(...)` rundt `TilbakekrevingConsumer.consume(...)` er mønsterfila: prodsignaturen krever `erDev`, testhjelperen defaulter den til `false`, og testene som faktisk bryr seg sender inn verdien selv.
- En default hvor **prod** er den som trenger verdien er selvsagt fortsatt i orden (`log: KLogger? = logger` gir prod den ekte loggeren, og testen overstyrer).
  Retningen er poenget: prod skal ha den riktige verdien uten hjelp fra testen.

**Hvorfor:** En default som er satt for testens skyld gjør at kallstedene i prod slutter å ta stilling til noe de burde ta stilling til, og feilen dukker opp som stille gal oppførsel i ett miljø i stedet for som en kompileringsfeil.

#### `@TestOnly` er samme lukt, og skal så godt som alltid unngås

Annotasjonen løser ingenting — den dokumenterer bare at testkode har lagt seg i en prodsignatur.
Sjekk alltid kallstedene først: flere `@TestOnly`-medlemmer viser seg å ikke ha noen brukere i det hele tatt, og skal da bare slettes.
Ellers dekker tre kurer praktisk talt alt:

- **Bekvemmelighetskonstruktører** (`Begrunnelse.createOrThrow` = `create(...)!!`) flyttes til testlaget som extension på companion-objektet, i en `*TestEx.kt` ved siden av typen.
  Kallstedene beholder `Type.metode(...)` og trenger kun en ny import.
- **Lesemetoder kun tester bruker** flyttes til testlaget med egen SQL.
  La mappingen bli i prod hvis prodspørringene bruker den — det er spørringen som er test-only, ikke mappingen.
- **Skrive-wrappere** som bare åpner en transaksjon rundt en companion-metode blir extensions på `PostgresSessionFactory` i testlaget.

### Testtaksonomi: prodstier og aggregat-disiplin

Kongstanken: all testtilstand bygges gjennom prodstiene.
Da kan en test ikke jukse seg til en tilstand prod aldri når, og vi slipper å holde et parallelt univers av tilstandskonstruksjon i synk med prodflytene for hånd.

1. **Ende-til-ende innenfor én sak er standarden.**
   Bygg tilstanden med route-testkonteksten og route-byggerne, ikke ved å persistere ObjectMother-objekter rett gjennom repoene.
   Rundturen («kan lagre og hente») dekkes av disse testene.
   Egne round-trip-tester per repo skal ikke skrives.

2. **Aggregat-tester er få, spesialiserte og isolerte.**
   De dekker det per-sak-testene ikke kan treffe: spørringer som velger ut på tvers av saker, typisk jobbkøer.
   Én fil per spørringsgruppe, navngitt `*AggregatTest`, og kjørt isolert.
   Fila bygger 2–3 saker gjennom prodstiene og asserter spørringens faktiske kontrakt: utvalgskriteriene, at `limit` respekteres, og sorteringen spørringen faktisk har.
   Har spørringen ingen `order by`, er rekkefølgen udefinert — assert på innhold og antall, ikke på sortering.

   Aggregat-testen erstatter ikke testen av per-sak-funksjonen.
   Jobber og consumere er naturlige black-box-innganger, og både jobben som sveiper på tvers og funksjonen som gjør arbeidet for én sak fortjener egen dekning.
   Det som skiller dem er lesekanalen, ikke om de får finnes: aggregat-testen leser køen, per-sak-testen leser tilstanden for sin egen sak.

3. **Ingen andre tester kaller `hent*(limit)`-metodene på repo-portene.**
   Kaller du en slik metode utenfor en `*AggregatTest`, er testen enten feilplassert, eller så tester den noe en e2e-test allerede dekker — eller så mangler den en lesekanal for én rad.
   I det siste tilfellet: les tilstanden gjennom domenemodellen hvis den er der, ellers med egen SQL (se «Data som skrives, men aldri leses ut i domenet»).
   Køspørringen er aldri riktig lesekanal for én sak.

4. **Unntak merkes eksplisitt med en kommentar i testfilen.**
   To kategorier er legitime: historiske eller korrupte dataformer (se «Negative databasetester» under), og rene db-typer uten domeneflyt.

**Motbildet er filter-krykka:**

```kotlin
// Ikke gjør dette:
repo.hentDeSomSkalJournalføres(limit = Int.MAX_VALUE)
    .filter { it.sakId == sak.id } shouldBe forventet
```

Mønsteret bruker en aggregatspørring som lesekanal for én sak, og slår i samme slengen av begge tingene spørringen finnes for.
`limit = Int.MAX_VALUE` gjør at grensen aldri testes, og `.filter { it.sakId == ... }` gjør at utvalget på tvers av saker aldri testes.
Testen består selv om spørringen plukker feil rader for alle andre saker enn sin egen.
Skal du teste rundturen, gjør det med en e2e-test; skal du teste spørringen, skriv en `*AggregatTest` uten filter.

#### Fakes er per test, jobber sveiper over hele skjemaet

Den vanligste kilden til flaky DB-tester: en fake-klient hører til én test-kontekst, mens jobbene henter på tvers av alle saker i skjemaet.

Styrer testen din en verdi på en fake (`var`-felt), **og** er den avhengig av utfallet av en jobb som sveiper på tvers, må testen kjøre isolert.
Ellers vil en annen test som kjører samme jobb parallelt plukke opp dine rader, spørre *sin* fake, og skrive et annet resultat enn det du satte opp.
Symptomet er en assertion som viser fakens defaultverdi i stedet for den du satte — og som passerer når testen kjøres alene.

Merk at det å bygge tilstand med en fake ikke i seg selv krever isolering.
Det er kombinasjonen av styrt fake-verdi og sveipende jobb som gjør det.

#### Full dekning på databaselaget

Målet er **100 % både linje- og grendekning (`CoverageUnit.LINE` og `CoverageUnit.BRANCH`) på hele databaselaget, tatt med route-testene som grunnsett.**
De to gatene står side om side fordi de fanger ulike hull: full grendekning sier ingenting om en linje uten grener, og full linjedekning sier ingenting om hvilken vei et vilkår ble tatt.
Tester utover grunnsettet kan bruke fakes.
Dekningen låses i en gate i `build.gradle.kts` slik at den ikke kan falle tilbake.

**Gaten skal være mønsterbasert, ikke en navneliste.**
I saksbehandling-api er den to mønstre: alt under en `infra/repo`-pakke (som dekker `*DbJson`-filene) pluss alt som heter `*Repo`, uansett hvor det ligger.
Kover matcher på fullt klassenavn, og `*` dekker også punktum — det finnes ingen `**`, og ett `*` spenner derfor over vilkårlig mange pakkenivåer.
Da er ny kode i databaselaget dekket som standard, og en pakke- eller navneendring kan ikke la dekningen forsvinne stille slik en includes-liste ville gjort.
Bootstrap som tilfeldigvis ligger i `infra/repo` (oppkobling og Flyway-oppsett) hører ikke til databaselaget, og settes i en kort, navngitt excludes-liste med begrunnelse.

Rekkefølgen når en `throw`/`require` i et repo står udekket:

1. **Nå den med en route-test** hvis tilstanden kan oppstå gjennom prodstiene.
2. **Ellers: skriv en negativ databasetest.** Muter databasen direkte til den ugyldige tilstanden og verifiser at repoet kaster. Det er helt greit — det er selve poenget med testen, og den hører i unntakskategorien over. Legg dem i en egen `*NegativTest`-fil med KDoc som sier hvorfor databasen muteres.
3. **Klarer vi ikke å trigge den heller, er `!!` på sin plass.** Typisk når en foreign key eller en unik indeks garanterer at raden finnes. En `requireNotNull` med melding ville da bare stått igjen som permanent udekket kode. Skriv en kommentar som sier hvilken garanti som gjør `!!` trygt.
   **Hviler `!!` på en constraint, skriv en test som verifiserer at constrainten finnes.** En insert eller update som skal feile, er nok. Garantien er ikke sterkere enn migreringen som holder den i live, og en droppet kolonne tar med seg både constrainten og gyldigheten til `!!`-et uten at noe annet slår ut.

Vurder også om domenelogikk i repoet kan flyttes inn i domenet.
Invarianter som håndheves på domenemodellen trenger ingen databasetest for å dekkes.

#### Data som skrives, men aldri leses ut i domenet

Noen felter finnes kun for å styre en jobb eller en spørring: de skrives inn, brukes i en `where`-klausul, og kommer aldri ut igjen på domenemodellen.
Køflagg er det typiske tilfellet.

**Det er en villet asymmetri, og domenemodellen skal ikke utvides for å gjøre slike felter observerbare.**
Å legge feltet på domenetypen kun for at en test skal kunne lese det, er å forurense modellen med noe prod ikke bruker.

Trenger en test å verifisere tilstanden, **skriv egen SQL i testen** og les kolonnen direkte.
Det er samme unntakskategori som de negative databasetestene: du går utenom domenemodellen med vitende og vilje, og KDoc-en i testen sier hvorfor.
Merk at dette er en *lesekanal for én rad* — det er noe annet enn å bruke jobbens køspørring som lesekanal, som fortsatt er filter-krykka.

Dekningen blir sjelden et problem: skrivestien kalles av prodflyten og lesestien av jobben, så repo-linjene dekkes uansett.
Er det likevel en linje som kun finnes for en spørring ingen prodsti kaller, er det dødt og skal slettes, ikke dekkes.

Skriver vi til en tabell ingen av våre lesestier rører — statistikktabellene leses kun av DVH — må insert-SQLen likevel testes.
Kjør skrivingen gjennom prodstien og les radene tilbake med egen SQL i testen.
Uten det ville en feil kolonnebinding aldri slått ut hos oss; den ville dukket opp som feil tall i datavarehuset.

#### Row hører i databasetesten, ren mapping i enhetstesten

Databaselaget har to slags kode, og de skal testes ulikt:

- **Alt som rører `Row`** — spørringer, radmapping, transaksjoner — skal gjennom en ekte databasetest.
- **Ren mapping** — jsonb-varianter, enum-oversettelser og felter med avansert mapping — skal ha enhetstester.
  Ligger mappingen i samme fil som postgres-koden, trekk den ut i en egen db-hjelpefil, så skillet blir synlig i filstrukturen.

**Enhetstesten skal pinne den faktiske strengen eller json-en, ikke bare rundturen.**
`x.toDb().toDomain() shouldBe x` er symmetrisk og passerer selv om en variant omdøpes i *begge* `when`-ene samtidig — og da er dataen som allerede ligger i databasen ulesbar uten at noe slår ut.
Skriv `Enum.entries.associateWith { it.toDb() } shouldBe mapOf(...)` med verdiene skrevet ut, eller assert hele json-strengen, og behold rundturen som en egen test for lesestien.
Navnet på disk er kontrakten mot data som allerede er lagret; dekningstall alene sier ingenting om at den holder.

**Tar du en snarvei av ytelseshensyn, skriv det i testen:** at dette er enhetstest framfor e2e, og hvorfor.
Typisk fordi hver enum-variant ville krevd sin egen flyt gjennom prodstien — en statusenum med nitten utfall koster nitten konstruerte feilsituasjoner — mens mappingen ikke rører postgres i det hele tatt.
Noter samtidig hva testen *ikke* sier: at varianten kan nås. En variant ingen prodsti produserer er død kode, og skal slettes framfor å dekkes.

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

> `tiltakspenger-libs` er unntaket: det deployes ikke til NAIS og bruker delte **convention-plugins** fra det inkluderte bygget `build-logic/` (`tiltakspenger.kotlin`, `tiltakspenger.bibliotek`, `tiltakspenger.dekning`, `tiltakspenger.githooks`) i stedet for å duplisere build-oppsettet i hver submodul. Se [`tiltakspenger-libs/AGENTS.md`](tiltakspenger-libs/AGENTS.md).

## Avhengigheter

- Minimér eksterne avhengigheter; bruk `testImplementation` / `compileOnly` der det er mulig
- Bruk version catalog der den finnes

## Auth og infra (backend-spesifikt)

- Autentisering via **NAIS Texas** (`tiltakspenger-libs:texas`) — token-introspeksjon og system-tokens
- **Pakking/Docker-image (felles konvensjon — hold identisk på tvers av repoene):** alle tjenester pakkes med `application`-pluginen (`mainClass.set(...)`) og `installDist` — **ingen fat-jar/shadowJar, ingen `Class-Path`-manifest**. Dockerfilen er ett steg, basert på distroless Java-baseimage (p.t. `gcr.io/distroless/java25-debian13`), kopierer `build/install/<app>/lib/*.jar` til `/app/lib/` med `--chmod=0755` (jars må være lesbare for `USER nobody`; ikke fjern) og starter med wildcard-classpath: `ENTRYPOINT ["java", "-cp", "/app/lib/*", "<mainClass>"]`. mainClass står bevisst to steder (`build.gradle.kts` + `ENTRYPOINT`) fordi distroless ikke har shell og dermed ikke kan kjøre start-scriptet fra `installDist` — hold dem i sync. Endres mønsteret, endre det i alle repoene samtidig.
- Kafka (Confluent) for hendelsesdrevet kommunikasjon
- PostgreSQL med Flyway for persistens
- Prometheus-metrikker via Micrometer (`io.micrometer:micrometer-registry-prometheus`)

