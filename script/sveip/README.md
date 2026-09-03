# sveip — klassifisering av hemmelighetssveipet

[navikt/gitleaks-wrapper](https://github.com/navikt/gitleaks-wrapper) er orgens delte verktøy for å
sveipe hele git-historikken i mange repoer med gitleaks og trufflehog. Den skriver én rapport per
repo og lar deg sette status (ok / violation / unsure) per treff i en terminal-TUI. Med tusenvis av
treff er TUI-en ikke veien: `klassifiser.py` setter statusene maskinelt etter reglene i
[`kriterier.md`](kriterier.md), skriver dem tilbake i wrapperens `review.json`, og bearbeider
resultatet til baselinebeviset vi trenger i kontrollrammeverket (K-EH.03).

Wrapperen eier sveipet; dette skriptet eier tolkningen. Ingenting av wrapperen er kopiert hit.
Tertial-hurtigkontrollen for ett repo er [`script/skann`](../skann/README.md).

## Bruk

```
# 1. Sveip i wrapperen (klon repoene i repos/, kjør analyze) — se README-en der
# 2. Klassifiser og bygg beviset, fra metarepoets rot:
./script/sveip/klassifiser.py            # tørrkjøring: fordeling og avvik, skriver ingenting
./script/sveip/klassifiser.py --write    # skriver wrapperens review.json og reports/sveip-<dato>/
```

Wrapperen finnes med `--wrapper <sti>` eller `GITLEAKS_WRAPPER` (standard `~/dev/nav/gitleaks-wrapper`).
Sveipdatoen leses fra rapportfilenes tidsstempel; `--dato YYYY-MM-DD` overstyrer. Kun stdlib, ingen
installasjon; `validate.py` (fnrvalidator-logikken) importeres fra wrapperen.

Ikke kjør wrapperens `run.py validate` — den setter samme statuser med grovere regler (alle H-numre blir
violation), og skriptet ville lese dem som manuelle avgjørelser.

## Det som kommer ut

`reports/` i metarepoets rot er gitignorert, på samme måte som i wrapperen. Hvert sveip får sin egen
mappe, `reports/sveip-<dato>/`:

| Fil | Innhold |
|---|---|
| `baselinebevis.md` | hovedrapporten: sammendrag, funn etter viktighet (🔴 fortsatt i HEAD, 🟡 bare i historikken — med pull requestene de er synlige i), beslutningen om historikken, 🟢 ikke funn, revisjonsspor. Én rad per forekomst med tomme vurderingskolonner for utvikleren. Limes inn i Confluence. |
| `pr-oppslag.json` | GitHubs svar på hvilke pull requests hver funn-commit hører til (`commits/<sha>/pulls`), mellomlagret så beviset er stabilt mellom kjøringer; slett fila for nytt oppslag |
| `begrunnelser.csv` | én rad per treff: status, kriteriekode, regel, verktøy, scope, fil, commit, linje, dato — aldri verdien |
| `ikke-reelle-numre.md` | 11-sifre som ikke kan være en person (ugyldig, Test-Norge, Dolly-serien), kommaseparert per repo — til innliming i [Dollys identvalidator](https://dolly.ekstern.dev.nav.no/identvalidator) som kontroll |
| `identvalidering.csv` | legges her for hånd: nedlastingen fra identvalidatoren etter innlimingen. Skriptet sammenholder den med lista ved neste kjøring og skriver resultatet (antall kontrollert, antall `erIProd`, avvik) inn i beviset |
| `rapport.txt` | utskriften fra wrapperens `run.py report` (skal vise `Todo: 0`) |
| `kriterier.md` | kopi av reglene slik de var da sveipet ble klassifisert |
| `review.json` | kopi av det som ble skrevet til wrapperen; `review_bak-<tid>.json` er det som lå der fra før |

Bildebevis per repo tas fra wrapperen: `python3 run.py report --repository-filter <repo>` — utskriften
har bare tall per regel og status.

## Verdier

Fødselsnumre i ekte serie, Nav-identer, e-poster og passord skrives aldri til stdout eller til filene
her; funn identifiseres med repo, commit, fil og linje, og gjenbruk av samme verdi vises med etikett
(F1…, I1…). Den som skal følge opp ser verdien i wrapperen (`run.py show`/`secrets` med
`--status-filter violation`). Ikke-reelle numre er ikke personopplysninger og listes med verdi.

## Manuelle avgjørelser

Statuser satt for hånd i wrapperens `review.json` vinner over reglene ved neste kjøring og listes i
baselinebeviset; `--regler-vinner` nullstiller. Presedensen står under «Statusene» i [`kriterier.md`](kriterier.md).
Er en regel feil eller mangler (ukjente regel-id-er får `unsure`), endres `kriterier.md` og skriptet
sammen; git-historikken på kriteriefila er sporet revisor trenger.

## Sikkerhet — hva skriptet gjør med det det leser

Rapportdata og filinnhold fra repoene parses som tekst (JSON, CSV, regex) og kjøres aldri.
Underprosesser startes uten shell; commit-SHA-er valideres som hex før de blir git-/API-argumenter, og
treffverdier sendes som egne argumenter etter `-e`/`-S` med `--` bak, så ingenting fra et repo kan bli et flagg.
Filnavn vaskes før de havner i markdown-tabellene, og celler i `begrunnelser.csv` vernes mot formelinjeksjon i regneark.
Skriptet stoler på det du alt stoler på når du kjører wrapperen: `validate.py` og `run.py` i klonen som
`--wrapper`/`GITLEAKS_WRAPPER` peker på, docker-imagene for versjonsoppslaget (kjørt med `--network none`)
og svaret fra `gh api` (kun `GET commits/<sha>/pulls`, med lesetokenet ditt).
Det endrer aldri noe i `repos/`; det skriver bare wrapperens `review.json` og filene under `reports/sveip-<dato>/`.
