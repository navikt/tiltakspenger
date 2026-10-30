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
Copilot CLI trenger et GitHub-token for å bekrefte tilgangen din og føre forbruket på kontoen din.
Inne i sandkassa har ikke Copilot CLI tilgang til nøkkelringen i macOS, så en innlogging med `/login` lagrer påloggingen i klartekst på disken.
Bruk derfor ikke `/login`, men lag et eget token som leses fra nøkkelringen utenfor sandkassa.
Det er et personlig token på din egen GitHub-konto, selv om Copilot-kvoten din kommer fra `navikt`.

Oppsettet beskytter tokenet på to måter:

- Inne i sandkassa ser agenten bare en plassholder, også om den følger ondsinnede instruksjoner fra kode, issues eller nettsider (prompt injection).
  Proxyen til `cplt` setter inn det ekte tokenet bare i forespørsler til GitHub-hoster.
  Plassholderen er verdiløs hvis den sendes andre steder.
- Utenfor sandkassa er det ekte tokenet tilgjengelig for prosesser du starter i terminalen, fordi `.zshrc` eksporterer det.
  Tokenet kan bare sende Copilot-forespørsler, ikke lese private repoer eller skrive noe sted.

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

`COPILOT_GITHUB_TOKEN` går foran `GH_TOKEN` og `GITHUB_TOKEN`, så Copilot CLI bruker dette tokenet selv om de andre variablene er satt.

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
