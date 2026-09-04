# skann-repo

Skanner et repo for innhold som ikke hører hjemme der: nettverksadresser
utenfor listen over godkjente verter, prosess- og socket-kall, hemmeligheter,
base64-blobber, fødselsnummer og kontonummer.

Bakgrunnen er publiseringsjobben i `tiltakspenger-libs`. Hele bygget — tester
inkludert — kjører i samme jobb som holder `packages`, `contents`, `id-token`
og `attestations: write`, og gjør det før artefaktene attesteres. En testfil
som ringer ut, starter en prosess eller bærer en ekte nøkkel har hele
publiseringsrettigheten tilgjengelig. Skriptet finner slikt før det står der.

## Bruk

```
./script/skann/skann-repo.py <repo-sti> [--sjekk a,b,...] [--info] \
    [--uten-test] [--uten-gitleaks] \
    [--unntak-prod <fil>] [--unntak-test <fil>]
```

Leser kun git-sporede filer (`git ls-files` i målrepoet) og hopper over
binærfiler. `--hjelp` viser bruksanvisningen.

> **Personverngaranti:** skanneren leser kun filer git sporer. Usporede og
> ignorerte filer åpnes aldri — en utviklers `.env`, IDE-oppsett, lokale dumper
> og alt annet `.gitignore` dekker, i rota som i undermapper, blir ikke lest
> uansett hva de inneholder. Garantien ligger i at filene hentes fra
> `git ls-files` og ingen andre steder, og den er dekket av `selvtest.py`.
> Skrives det om til filsystemvandring, faller den.

Exit-koder: `0` ingen funn, `1` funn, `2` feil i argumenter eller unntaksliste.

```
./script/skann/skann-repo.py tiltakspenger-libs
./script/skann/skann-repo.py tiltakspenger-soknad --sjekk fnr,kontonummer --info
```

## Kjøringsbevis

Hver kjøring starter med en header som gjør utskriften selvdokumenterende:
tidspunkt med tidssone, repoet, den eksakte commiten tilstanden gjelder (kort
og full SHA), gren, om arbeidstreet har endringer utenfor commiten, hvilken
commit skanneren selv står på, og versjonen av hvert eksternt verktøy som
deltok.

```
========================================================================
skann-repo — kjøringsbevis
  Tidspunkt   : 2026-09-02 16:12:25 CEST (UTC+0200)
  Repo        : tiltakspenger-iac
  Sti         : /Users/.../tiltakspenger-iac
  Commit      : cb5b54f  (cb5b54fefc60d1462d0523dd0a084324c54eb957)
  Gren        : main
  Arbeidstre  : rent
  Skannerkode : 0ad790f  (0ad790f05fd0e83b456fd5e46853220c420a5c64)
  gitleaks    : 8.30.1 (/Users/.../gitleaks)
========================================================================
```

En lagret utskrift kan dermed stå alene som dokumentasjon på hva som ble
skannet, når, og med hva.

## Hoppet over

Kjøringen avsluttes alltid med en «Hoppet over»-blokk, også når ingenting ble
hoppet over. Ingen sjekk skal kunne falle ut uten at utskriften sier fra:

| Grunn | Når |
|---|---|
| `valgt bort med --sjekk` | brukeren valgte et smalere sett |
| `slått av med --uten-gitleaks` | verktøyet er avslått med flagg |
| `verktøy mangler (gitleaks ikke på PATH)` | binæren finnes ikke |
| `test-scope utelatt med --uten-test` | kun prod-filer ble lest |

Et manglende verktøy gir aldri exit-feil — resten av sjekkene kjører, og
blokka forteller hva som ikke ble gjort.

`--uten-test` leser kun prod-klassifiserte filer. Antall hoppede testfiler
står i «Skannet»-linja.

## Filstruktur

Skriptet er delt i en tynn inngang og en pakke ved siden av. Kun stdlib, ingen
installasjon — inngangen legger sin egen mappe på `sys.path`.

| Fil | Innhold |
|---|---|
| `skann-repo.py` | kjørbar inngang: argumenter, filgjennomgang, utskrift |
| `skannlib/spraak.py` | filtyper, kommentarstripping, prod/test-klassifisering |
| `skannlib/siffer.py` | mod11, fnr, kontonummer, plassholdere, kontekstvakter |
| `skannlib/sjekker.py` | reglene, én funksjon per sjekk |
| `skannlib/unntak.py` | unntakslistene, begrunnelseskravet, statistikken |
| `selvtest.py` | bygger et fixtur-repo i tempdir og sjekker kjerneatferden |

## Selvtest

```
./script/skann/selvtest.py
```

Bygger et fixtur-repo i en midlertidig katalog, kjører skanneren mot det som
subprocess, og sjekker 63 punkter: personverngarantien, prod/test-skillet,
datovalideringen, kommentarklippingen, compose- og env-klassifiseringen,
tjenestenavn i klyngen, pakkeregistre og skjemaverter, lockfil-hoppet,
navneformene hemmelighetssjekken slipper, de scope-delte unntakslistene,
bevis-headeren,
«Hoppet over»-blokka i alle varianter, `--uten-test`, exit-kodene og ett
kjernetreff per sjekk. Fixturen genereres i stedet for å
ligge i git — plantede tokens og identer ville trigget GitHubs secret scanning.
`--behold` lar fixturen stå igjen når noe feiler.

## Sjekkene

| Sjekk | Ser etter | Filtyper |
|---|---|---|
| `nettverk` | URL-er med ikke-godkjent vert — hva som er godkjent avhenger av scope, se under | `KODEFILER` i `spraak.py`: `.kt` `.kts` `.java` `.ts` `.tsx` `.js` `.mjs` `.cjs` `.astro` `.rs` `.py` `.sh` `.yml` `.yaml` `.tf` `.hcl` `.toml` |
| `prosess` | prosess-, socket- og native-kall, med egne mønstre per språk | jvm, rust, node, python |
| `hemmeligheter` | privatnøkkel-blokker, `ghp_`/`gho_`/`github_pat_`, `AKIA…`, `xox[baprs]-`, `NAIS_`/`AZURE_`-navn satt til en lang literal. Verdier som selv er navn treffer ikke: små bokstaver i ledd, et miljøvariabelnavn (`AZURE_APP_CLIENT_ID`) eller en container-image-referanse (`ghcr.io/navikt/app:tag`) | alle |
| `jwt` | JWT-lignende strenger — egen sjekk, fordi testfixturer har legitime | alle |
| `base64` | base64-literaler på 60 tegn eller mer | alle |
| `fnr` | 11-sifrede tall — se prod/test-skillet under | alle |
| `kontonummer` | 11 siffer som validerer mod11 som norsk kontonummer | alle |
| `gitleaks` | hele git-historikken, via gitleaks-binæren på PATH | ekstern |

Kommentarlinjer og etterfølgende kommentarer klippes bort før `nettverk` og
`prosess` kjører — en dokumentasjonslenke i en KDoc er ikke et utgående kall.
Versjonsnumre, maven-koordinater og sifre som er del av et lengre tall eller en
identifikator treffer ikke `fnr` og `kontonummer`.

### gitleaks

`gitleaks` er den eneste sjekken som ikke leser filer selv. Den sheller ut til
gitleaks-binæren og skanner **hele git-historikken**, ikke bare tilstanden nå —
det er der lekkede hemmeligheter faktisk ligger. Kjøres med `--redact`, og vi
plukker kun regel-id, fil, linje og commit ut av rapporten. **Hemmelighetens
verdi kommer aldri ut av skanneren**, heller ikke i matchtekst-kolonnen, som
bærer regel-id-en.

Binæren må ligge på PATH. Gjør den ikke det, hopper sjekken over med beskjed.
Slå den av med `--uten-gitleaks` når du vil ha en rask kjøring.

For flerrepo-sveip over hele flåten, bruk [navikt/gitleaks-wrapper]
(https://github.com/navikt/gitleaks-wrapper) — orgens delte verktøy, som også
kjører trufflehog og har Nav-spesifikke regler. Sjekken her er
tertial-hurtigkontrollen for ett repo, ikke en erstatning for den.

### Språk og økosystemer

Flåten er blandet, og sjekkene skal bety det samme overalt.

| Familie | Filtyper | Prosessmønstre |
|---|---|---|
| JVM | `.kt` `.kts` `.java` | `Runtime.exec`, `ProcessBuilder`, `java.net.*Socket`, `System.loadLibrary` |
| Rust | `.rs` | `std::process::Command`, `Command::new`, `TcpStream`/`TcpListener`/`UdpSocket`/`UnixStream`, `libloading`/`dlopen` |
| Node | `.ts` `.tsx` `.js` `.mjs` `.cjs` `.astro` | `child_process`, `execSync`/`execFileSync`/`spawnSync`/`execFile`, `net.Socket`, `dgram` |
| Python | `.py` | `subprocess.run`/`Popen`/`call`/`check_*`, `os.system`/`popen`/`exec*`, `socket.socket`, `ctypes.CDLL` |

Mønstrene er valgt for signal framfor bredde. Bare `exec(` og `spawn(` er
utelatt: `regex.exec(...)` er dagligdags i JavaScript og ville druknet de ekte
funnene. På samme måte kreves navngitte `subprocess`-kall, slik at et
`except subprocess.CalledProcessError` ikke leses som et prosesskall.

Kommentar- og strengsyntaks følger familien. I Kotlin, Java og Rust er `"` det
eneste strengtegnet, fordi `'` der er tegnliteral og apostrof. I JavaScript og
TypeScript teller også `'` og backtick — uten dem ville `const x = '//';`
kuttet resten av linja og skjult et kall etter den. Shell, Python og YAML
bruker `#` med både `"` og `'`, og Terraform og HCL godtar begge
kommentarformene.

## Produksjonskode og testkode

Sjekkene er strengest i prod, og skillet gjøres i `spraak.er_testfil`.

**Testkode** er `src/test/` og `src/testFixtures/`, en testkatalog i repo-rota
(`tests/` eller `test/` — ankeret er bevisst, ellers ville en Kotlin-pakke som
heter `test` under `src/main` blitt feilklassifisert), testmoduler kjent på
navnet (`*-test`, `*test-common`, `*-test-core`), `mock-req-res/`, og
frontendmønstrene `*.test.*`, `*.spec.*` og `*.stories.*` (uten ende-anker, så
`foo.test.d.ts` og `foo.spec.ts.snap` også teller — Storybook-filer hører til av
samme grunn: de kjører i katalogen, aldri i det som deployes), `__tests__/`, `e2e/`, `playwright/`,
`fixtures/`, `testdata/` og `test-data/`. I tillegg testriggenes egen
konfigurasjon: `playwright.config.*`, `vitest.config.*` og `jest.config.*` —
de kjører testene og blir aldri med i deployment. Bygg- og lintconfiger
(`vite`, `next`, `astro`, `eslint`) er derimot prod.

Compose-oppsett (`docker-compose*.yml`, `compose*.yml`) og maler for
miljøvariabler (`.env-template`, `.env.example`, `.env.tests` og liknende) er
også testkode: Nais deployer kun via manifester, så de følger aldri med noe
sted. Merk unntaket — `.env.prod`, `.env.dev` og `.env.demo` er ekte
byggkonfigurasjon, og `NEXT_PUBLIC_`-verdiene der bakes inn i bundelen som
skipes. De er prod. En ren `.env` er usporet og leses aldri uansett.

**Alt annet er prod** — også Nais-manifester, Terraform, docker-compose,
skript, byggfiler og dokumentasjon.

> **Begrensning:** en Rust-fil med `#[cfg(test)]`-modul inne i `src/` regnes
> som prod. Testkoden ligger da i samme fil som produksjonskoden, og skriptet
> skiller ikke på blokknivå.

### Godkjente verter

Nettverkssjekken bruker samme prod/test-skille, og lista er ulik i de to.

| Scope | Godkjent |
|---|---|
| test | `localhost`, `127.0.0.1`, `0.0.0.0`, `::1`, `host.docker.internal`, `example.com/org/net`, RFC 5737-adressene, og suffiksene `.test`, `.local`, `.localhost`, `.invalid`, `.example`, `.example.com/org/net`, `.nav.no`, `.adeo.no`, `.nais.io`. Loopback og private adresser godkjennes også via `ipaddress`. |
| prod | `.nav.no`, `.adeo.no` og `.nais.io` (apex inkludert), apper adressert på tjenestenavn i klyngen, suffiksene `.svc.cluster.local` og `.svc.nais.local`, kjente pakkeregistre, skjemaverter og `login.microsoftonline.com`/`graph.microsoft.com`. Alt annet er funn — også `localhost`, `127.0.0.1`, `0.0.0.0`, `::1` og `host.docker.internal`. |

Fire lister gjelder i **begge** scope, fordi noe som er greit i koden som
deployes ikke kan være strengere vurdert i en testfil:

| Liste | Innhold | Hvorfor |
|---|---|---|
| tjenestenavn i klyngen | `app`, `app.namespace`, `*.svc.cluster.local`, `*.svc.nais.local` | Nais' service discovery |
| pakkeregistre | npmjs, GitHub Packages, Maven Central, Gradle-plugins, Confluent, crates.io, PyPI | bygget henter avhengigheter, appen ringer ikke ut |
| skjemaverter | `www.w3.org`, `json-schema.org`, `schemas.xmlsoap.org`, `xmlns.jcp.org` | navnerom, aldri et oppslag |
| identitetsleverandør | `login.microsoftonline.com`, `graph.microsoft.com` | plattformens egen |

Ukjente pakkeregistre er fortsatt funn — der ligger forsyningskjede-signalet.
Altinn, Brønnøysund, Maskinporten og andre partnerintegrasjoner varierer per
team og hører hjemme i unntakslista med begrunnelse, ikke i lista over.

Lockfiler (`pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`, `Cargo.lock`,
`*.lockfile`) leses ikke av nettverkssjekken i det hele tatt. De er
maskingenererte, og registeret de peker på er bestemt i `.npmrc`,
`pnpm-workspace.yaml` eller byggfila. De andre sjekkene leser dem fortsatt.

En testfixtur skal kunne peke på hva som helst fiktivt. I prod er lista
minimal, av samme grunn som 11-sifferregelen er absolutt: en lokal adresse i
kode som blir med i artefakten er en lokal-profildefault på avveie.
Dokumentasjonsadresser hører i kommentarer, og de strippes allerede.

Interpolerte verter (`$`, `{`, `%`) godkjennes i begge scope — der er strengen
ikke en adresse i det hele tatt.

**Tjenestenavn i klyngen er en heuristikk.** Ett ledd (`http://amt-deltaker`)
godkjennes, og to ledd (`http://amt-deltaker.amt`) når siste ledd ikke er et
kjent toppdomene — `TOPPDOMENER` i `sjekker.py` er den eksplisitte lista, så
`example.com` og `evil.io` er fortsatt funn. Loopback-navnene er unntatt:
`localhost` og `host.docker.internal` er funn i prod, det samme er alt som
`ipaddress` leser som en IP-adresse.

Prisen står i koden: en teststubb som `http://test` eller `http://pdl` i
produksjonskode slipper nå gjennom, og et namespace som deler navn med et
toppdomene ville blitt lest som et domene. Alternativet — å binde formen til
ett teams appnavnprefiks — gjør skriptet ubrukelig for alle andre.

`.local` står bevisst ikke i prod-lista. Målt i flåten finnes `elector.local`
(Nais leader elector) og `texas.local` kun i testkode, og målingen er gjentatt
over 69 repoer i tre naboteam med samme svar. Dukker ekte prodbruk opp, hører
den hjemme som en begrunnet unntaksoppføring, ikke som en oppmyking av lista.

### Den absolutte prod-regelen

**I produksjonskode er ethvert frittstående 11-sifret tall et funn.** Ingen
mod11-validering, ingen unntak for plassholdere, og INFO-nivået finnes ikke i
prod. En plassholder som `99999999999` er like uønsket der som et ekte nummer:
den inviterer til at noen erstatter den med et virkelig nummer senere. En
mod11-sjekk ville dessuten sluppet gjennom både avkortede identer og tall som
blir gyldige etter en tastefeil.

Validerer tallet i tillegg som fnr eller kontonummer, står det i meldingen — da
er alvoret høyere.

Kun kontekstvaktene gjelder: sifre som er del av et lengre tall, en
maven-koordinat, en versjon eller en identifikator er ikke frittstående tall og
rapporteres ikke.

**I testkode** står den mildere regelen: tallet valideres mot mod11 etter begge
ordningene, plassholdersekvenser forkastes, og syntetiske serier rapporteres
som INFO.

### To ordninger for kontrollsifrene

Skatteetaten frigjør det **første** kontrollsifferet for å utvide
nummerrommet. Fra 2032 er k2 alene fasiten, og Dolly deler allerede ut slike
numre. En sjekk som krever begge kontrollsifrene er blind for dem.

| Ordning | Krav | Melding |
|---|---|---|
| gammel | k1 og k2 stemmer | `gyldig fødselsnummer (gammel ordning), …` |
| 2032 | kun k2 stemmer | `gyldig fødselsnummer (2032-ordning, kan også være kontonummer), …` |

Månedsklassifiseringen er den samme for begge — 01–12 ekte serie, 41–52 Dolly,
81–92 Test-Norge — og D-nummer (dag + 40) dekkes i begge.

**Fikk du et fnr-funn?** Skanneren sier bare at nummeret har formen og
validerer; den slår ikke opp om det er tildelt noen. Det kan du gjøre selv:

- [Skatteetatens PID-validering](https://www.skatteetaten.no/deling/folkeregisteret/pid/validering/)
- [Dollys identvalidator](https://dolly.ekstern.dev.nav.no/identvalidator)

Et nummer i ekte serie er et funn uansett hva oppslaget svarer. Er det ikke
tildelt i dag, kan det bli det i morgen — nummerserien er den samme.

**Kontonummer bruker samme mod11-vekter som k2.** Et nummer som kun validerer
etter 2032-ordningen har derfor ikke sterkere validering enn et kontonummer —
det er datoformen i de fire første sifrene som skiller dem. Der vinner `fnr`,
som er den alvorligste tolkningen, og meldingen sier fra om tvetydigheten.
`kontonummer` rapporterer bare det `fnr` ikke tok.

Prisen for 2032-utvidelsen er målt: på tilfeldige 11-sifrede tall går andelen
som rapporteres som fnr i testkode fra 0,17 % til 1,95 %, rundt elleve ganger.
To kontekstkrav holder støyen nede uten å svekke selve valideringen:
sifferrekka må ikke grense til en bokstav eller `_` (da er den halen av en id
eller digest, som i en lockfil), og den må ikke være en plassholdersekvens —
åtte sifre på rad som er like, øker eller synker med ett.

Plassholderfilteret er en bevisst støyavveining, ikke en matematisk sannhet.
Et gyldig nummer *kan* ha den formen, og noen få gjør det. Uten filteret kommer
rundt 355 slike treff i flåten, og de drukner de ekte. Derfor er det koblet ut
i prod, der ethvert 11-sifret tall uansett er et funn.

## Unntakslistene

To filer i denne mappa, én per scope:

| Fil | Gjelder |
|---|---|
| `skann-unntak-prod.txt` | treff i filer klassifisert som produksjonskode |
| `skann-unntak-test.txt` | treff i filer klassifisert som testkode |

Delingen er poenget: **et testunntak kan aldri skjule et funn i
produksjonskode.** Havner en oppføring i feil fil, gir den ingen treff og vises
som ubrukt i statistikken.

Begge er **skriptets** lister, ikke det enkelte repoets: én fil i metarepoet
dekker hele flåten. De leses automatisk; `--unntak-prod` og `--unntak-test`
overstyrer hver sin.

Format, én oppføring per linje:

```
sjekk-id regex             gjelder alle repoer
repo-navn/sjekk-id regex   gjelder kun det repoet (basename av skannet sti)
```

Regexen matches mot matchteksten og mot `sti:matchtekst`.

**Hver oppføring må ha en `#`-begrunnelse på linja over.** Uten den feiler
skriptet med exit 2 og peker på linja. Det er samme disiplin som
zizmor-unntakene våre, og av samme grunn: et unntak uten begrunnelse er et
unntak ingen tør fjerne igjen. En linje med bare `#` hører til en flerlinjes
begrunnelse; en blank linje avslutter blokka.

Rekkefølgen på arbeidet er:

1. Er funnet reelt — fiks det i repoet.
2. Er den falske positiven realistisk for flere repoer — fiks mønsteret i
   skriptet. Det er førstevalget; en liste over godkjente verter som vokser er
   bedre enn en unntaksliste som vokser.
3. Først når ingen av delene gjelder: legg oppføringen i riktig liste, med
   begrunnelse.

## Statistikken er styringssignalet

Hver kjøring avslutter med, per liste, hvor mange oppføringer den har, hvor
mange som gjelder repoet og de valgte sjekkene, hvor mange treff hver oppføring
undertrykte, og hvilke som ikke traff noe.

```
Unntaksstatistikk
  [prod] .../skann-unntak-prod.txt
    N oppføringer, M gjelder tiltakspenger-libs og de valgte sjekkene, K treff undertrykt.
         3  tiltakspenger-libs/prosess lokal-oppstart/...  (linje 37)
         ...
    Ubrukte (1 oppføringer — kandidater for opprydding …):
            tiltakspenger-libs/nettverk gammel-tjeneste\.example\.com  (linje 61)
```

To ting å se etter. **Ubrukte oppføringer** er unntak for kode som ikke finnes
lenger — de skal slettes, ellers dekker de noe nytt en dag uten at noen har
bestemt det. **En voksende liste** betyr at skriptet melder feil om ting vi
ikke akter å gjøre noe med; da skal enten mønsteret strammes eller sjekken tas
opp til vurdering. Bruk tallene som terskel, ikke som pynt.
