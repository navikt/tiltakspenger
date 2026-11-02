# Eget token for Copilot CLI ved bruk av nav-pilot

Slik setter du opp et eget GitHub-token for Copilot CLI i nav-pilot, lagret i nøkkelringen på macOS.

[`nav-pilot`](https://ki-utvikling.nav.no/nav-pilot) er Navs verktøy for kodeagenter.
Det installerer agenter, skills og instruksjoner med Nav-kontekst.
Når du bruker en kodeagent på Nav-utstyr, skal agenten kjøre i en sandkasse eller tilsvarende isolasjon.
Dette er et [krav](https://ki-utvikling.nav.no/nyheter/sandboxing-er-pakrevd-pa-nav-utstyr), **ikke** et valgfritt sikkerhetstiltak.
`cplt` er den anbefalte og enkleste måten å oppfylle kravet på.

Installer begge med:

```sh
brew install navikt/tap/nav-pilot navikt/tap/cplt
```

## Hvorfor eget token

Når du starter `nav-pilot`, kjører Copilot CLI inne i `cplt`.
Etter at du har satt opp [lesetoken for `gh`](gh-lesetoken.md) i steg 3, er det to ulike tokens i sving med hver sin oppgave:

- **Tokenet fra steg 3 ([lesetoken for `gh`](gh-lesetoken.md))** har `navikt` som eier og lesetilgang til utvalgte repoer.
  Det brukes av `gh` i terminalen din, og av agenten inne i `cplt` (gjennom `cplt` sin `gh`-guard) når den kjører `gh` for å lese issues, PR-er og workflow-kjøringer.
  Det er sånn det skal være.
- **Tokenet i denne oppskriften (steg 4)** er et personlig token på din egen GitHub-bruker med kun `Copilot Requests: Read-only`, selv om Copilot-kvoten din kommer fra `navikt`.
  Det brukes bare av selve Copilot CLI for å bekrefte Copilot-tilgangen din og føre forbruket på kontoen din.
  Det har ingen tilgang til `navikt` eller private repoer.

Uten eget oppsett prøver `cplt` å logge inn Copilot CLI med tokenet fra `gh`, men et token med `navikt` som `Resource owner` kan ikke ha kontotillatelsen `Copilot Requests`.
Inne i sandkassa har heller ikke Copilot CLI tilgang til nøkkelringen i macOS, så en innlogging med `/login` lagrer påloggingen i klartekst på disken.
Bruk derfor ikke `/login`, men lag et eget token som leses fra nøkkelringen utenfor sandkassa.

Oppsettet beskytter tokenet på to måter:

- Inne i sandkassa ser agenten bare en plassholder, også om den følger ondsinnede instruksjoner fra kode, issues eller nettsider (prompt injection).
  Proxyen til `cplt` setter inn det ekte tokenet bare i forespørsler til GitHub-hosts.
  Plassholderen er verdiløs hvis den sendes andre steder.
- Utenfor sandkassa er det ekte tokenet tilgjengelig for prosesser du starter i terminalen, fordi `.zshrc` eksporterer det ved oppstart.
  Tokenet kan bare sende Copilot-forespørsler, ikke lese private repoer eller skrive noe sted, så det verste en annen prosess kan gjøre er å stjele av Copilot-kvoten din.
  Vil du unngå at variabelen ligger fast i miljøet ved oppstart, kan du legge en funksjon i `.zshrc` som henter tokenet kun når `nav-pilot` starter.

## 1. Lag tokenet

<https://github.com/settings/personal-access-tokens/new>

| Felt                | Verdi                                                    |
| ------------------- | -------------------------------------------------------- |
| Resource owner      | Din egen bruker, ikke `navikt`                           |
| Repository access   | Public repositories                                      |
| Account permissions | `Copilot Requests: Read-only`, alt annet `No access`     |

## 2. Legg tokenet i nøkkelringen

```sh
security add-generic-password -U -a "$USER" -s copilot-cli-pat -w
```

Lim inn tokenet når du blir spurt.
Når `-w` står sist, ber kommandoen om verdien, og tokenet havner verken i shell-historikken eller i prosesslista.
Med `-U` overskriver du en eksisterende oppføring, så du kan bruke samme kommando når du fornyer tokenet.

## 3. Eksporter tokenet i `~/.zshrc`

Legg denne linjen til i `~/.zshrc`:

```sh
export COPILOT_GITHUB_TOKEN="$(security find-generic-password -a "$USER" -s copilot-cli-pat -w 2>/dev/null)"
```

Copilot CLI støtter tre miljøvariabler for pålogging: `COPILOT_GITHUB_TOKEN`, `GH_TOKEN` og `GITHUB_TOKEN`.
`GH_TOKEN` og `GITHUB_TOKEN` er generelle GitHub-variabler som også leses av `gh` og andre verktøy, der de overstyrer tokenet i nøkkelringen.
Legger du Copilot-tokenet i en av dem, vil både `gh` i terminalen og agentens `gh`-kall i `cplt` bruke det i stedet for lesetokenet fra [steg 3](gh-lesetoken.md), og feile mot `navikt`-repoene.
Bruk derfor `COPILOT_GITHUB_TOKEN`, som bare leses av Copilot CLI.

## 4. Send tokenet inn i `cplt`

Legg inn verdiene under i `~/.config/cplt/config.toml`.
Hvis `[sandbox]` eller `[proxy]` allerede finnes, oppdater verdiene i de eksisterende seksjonene i stedet for å opprette dem på nytt.
Behold eventuelle andre variabler i `pass_env`.

```toml
[sandbox]
pass_env = ["COPILOT_GITHUB_TOKEN"]

[proxy]
inject_github_token = true
```

`pass_env` slipper variabelen inn til `cplt`, og `inject_github_token` bytter verdien ut med en plassholder før agenten starter.

```sh
cplt config validate
```

## 5. Verifiser

Gå til et terminalvindu utenfor `nav-pilot`, stå i et git-repo (siden `cplt` nekter å starte i `~`), og kjør:

```sh
source ~/.zshrc
printf 'Ekte token (utenfor sandkassa): '
printf %s "$COPILOT_GITHUB_TOKEN" | shasum -a 256 | cut -c1-12
printf 'Plassholder (inne i cplt): '
cplt exec -- sh -c 'printf %s "$COPILOT_GITHUB_TOKEN" | shasum -a 256 | cut -c1-12'
```

`Ekte token (utenfor sandkassa)` er hashen av GitHub-tokenet som terminalen har lest fra nøkkelringen.
`Plassholder (inne i cplt)` er hashen av verdien agenten får se i stedet for det ekte tokenet.
Kommandoene viser bare de første 12 tegnene i hver SHA-256-hash, ikke selve tokenet eller plassholderen.
Du skal få to ulike hasher, og ingen av dem skal være `e3b0c44298fc` (som er hashen av en tom streng):

- Er hashen for `Ekte token` lik `e3b0c44298fc`, er `COPILOT_GITHUB_TOKEN` tom i terminalen din (sjekk steg 2 og 3).
- Er hashen for `Plassholder` lik `e3b0c44298fc`, ble variabelen strippet av sandkassa (sjekk `pass_env` i steg 4).
- Er begge hashene like (og ikke `e3b0c44298fc`), ser agenten det ekte tokenet (sjekk `inject_github_token` i steg 4).

Start til slutt `nav-pilot` og sjekk at Copilot svarer.

## Fornyelse

Forny først tokenet på [GitHub](https://github.com/settings/personal-access-tokens).
Kjør deretter steg 2 på nytt med det nye tokenet, og åpne en ny terminal.
