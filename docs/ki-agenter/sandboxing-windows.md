# Sandboxet agent på Windows

Kravet står i [Sandboxing og isolasjon er påkrevd på Nav-utstyr](https://ki-utvikling.nav.no/nyheter/sandboxing-er-pakrevd-pa-nav-utstyr).
Denne oppskriften er rent praktisk: hvordan du får en sandboxet agent til å kjøre når maskinen din er en Windows-maskin.

**Ikke testet.**
Den er skrevet fra dokumentasjonen til WSL, Copilot CLI og cplt, uten at en Windows-maskin har vært gjennom stegene.
Virker noe annerledes enn beskrevet, rett det opp her.

## Hvorfor det blir WSL

[cplt](https://ki-utvikling.nav.no/cplt) er bygget på operativsystemets egne mekanismer — Seatbelt på macOS, Landlock og seccomp-BPF på Linux.
Det finnes ingen Windows-versjon.

Copilot CLI har en innebygd lokal sandbox, men ifølge [GitHubs dokumentasjon](https://docs.github.com/en/copilot/concepts/about-cloud-and-local-sandboxes) krever den et Windows Insiders-bygg på Windows.

WSL2 kjører en ekte Linux-kjerne på Windows, og Landlock har vært med i den kjernen siden 5.15.57.1 i mai 2022 (se [kjerneutgivelsene](https://learn.microsoft.com/en-us/windows/wsl/kernel-release-notes)).
Veien videre er altså å kjøre agenten inne i WSL2, med cplt rundt seg.

| | Windows direkte | Inne i WSL2 |
|---|---|---|
| cplt | Finnes ikke | Landlock, ingen eksterne avhengigheter |
| Copilot CLI `/sandbox` | Kun på Insiders-bygg | Bruker `bwrap`, som krever unprivileged user namespaces |

## 1. Installer WSL2

I PowerShell som administrator:

```powershell
wsl --install
wsl --update
```

`wsl --install` slår på funksjonen og installerer Ubuntu.
Maskinen må startes på nytt underveis.

```powershell
wsl --version
```

Kommandoene krever administratorrettigheter.
Er de sperret på maskinen din, er det en sak for IT — resten av oppskriften forutsetter at WSL2 er på plass.

## 2. Sjekk at kjernen har Landlock

Start Ubuntu fra Start-menyen, eller kjør `wsl` i et terminalvindu:

```sh
uname -r
cat /sys/kernel/security/lsm
```

`uname -r` skal vise noe i retning `6.6.x-microsoft-standard-WSL2`, og lista fra `lsm` skal inneholde `landlock`.
Står ikke `landlock` der, kjør `wsl --update` fra PowerShell og prøv på nytt.

Kjerner eldre enn 6.7 har ikke TCP-portfiltrering i Landlock.
Det betyr ikke at nettverket står åpent — cplt kjører en proxy som standard, og den håndterer domenefiltrering uavhengig av kjerneversjon.

## 3. Installer Copilot CLI inne i WSL

Installasjonen skal skje i Ubuntu, ikke i Windows.
Et Copilot CLI installert med `winget` kjører på Windows-siden og kommer aldri innenfor sandboxen.

```sh
curl -fsSL https://gh.io/copilot-install | bash
```

Binæren havner i `~/.local/bin`.
Ubuntu legger den katalogen på PATH via `~/.profile`, men bare hvis den fantes da du logget inn — så start skallet på nytt hvis `copilot` ikke finnes:

```sh
exec bash -l
copilot --version
```

Logg inn én gang før sandboxen kommer på plass:

```sh
copilot
```

Er du ikke innlogget fra før, skriver du `/login` og følger instruksjonene.
Nettleseren åpner seg på Windows-siden.

## 4. Installer cplt

```sh
curl -fsSL https://raw.githubusercontent.com/navikt/cplt/main/install.sh | bash
cplt doctor
```

Skriptet bruker Homebrew hvis det finnes, ellers laster det ned binæren for `x86_64-unknown-linux-gnu`.
I en vanlig WSL-Ubuntu uten Homebrew blir det nedlasting, og også denne havner i `~/.local/bin`.

`cplt doctor` rapporterer hvilke kjøretidsmiljøer den fant og hvilke tillatelser de trenger.
Er det noe som ikke virker under WSL, er det her det viser seg først.

## 5. La `copilot` bety den sandboxede varianten

```sh
cplt --shell-install
exec bash -l
```

Kommandoen legger `eval "$(cplt --shell-setup)"` i `~/.bashrc`, og er trygg å kjøre flere ganger.
Etter dette går `copilot` gjennom cplt.

Uten aliaset er `cplt` selv kommandoen:

```sh
cplt -- -p "fiks testene"
cplt --agent shell            # interaktivt sandboxet skall, uten agent
cplt exec -- ./gradlew test   # sandbox en vilkårlig kommando
```

## 6. Legg koden i Linux-filsystemet

Klon repoene under hjemmekatalogen i Ubuntu (`~/dev/…`), ikke under `/mnt/c/`.
Windows-disken er montert over et filsystemlag som er tregt for mange små filer, og et Gradle- eller Node-prosjekt merker det godt.

Fra Windows når du de samme filene på `\\wsl$\Ubuntu\home\<brukernavn>`, og VS Code åpner dem med utvidelsen **WSL**.

## 7. Verifiser at sandboxen stenger

cplt kjører en startsjekk som verifiserer at restriksjonene er aktive.
Den kan slås av med `--no-validate` — la være.

En konkret test:

```sh
mkdir -p ~/.ssh && echo hemmelig > ~/.ssh/cplt-test
cplt exec -- cat ~/.ssh/cplt-test
rm ~/.ssh/cplt-test
```

Lesingen skal nektes.
Kommer `hemmelig` ut, kjører agenten uten sandbox.

## Per-repo-config

```sh
cplt init --write
cplt trust accept --all
```

`cplt init --write` skanner prosjektet og skriver en `.cplt.toml` med tillatelsene byggeverktøyene faktisk trenger.
Fila committes, slik at alle som kjører cplt i repoet får samme oppsett — se [cplt — team-config og auto-generert sandbox](https://ki-utvikling.nav.no/nyheter/cplt-team-config).

## Dette virker bevisst ikke

Et utvalg fra [Known impacts](https://github.com/navikt/cplt#known-impacts) i cplt:

| Hva | Fiks |
|---|---|
| `.env`-filer er blokkert | `cplt config set sandbox.allow_env_files true` |
| npm-postinstall-hooks er blokkert | `cplt config set sandbox.allow_lifecycle_scripts true` |
| Tilkobling til localhost er blokkert | `cplt config set allow.localhost 3000` |
| Docker er blokkert | `cplt config set sandbox.allow_docker true` |
| GPG-signering er slått av | `cplt config set sandbox.allow_gpg_signing true` |
| MockK/Mockito feiler på JVM | `cplt config set sandbox.allow_jvm_attach true` |

SSH-agenten er blokkert i sandboxen, så `git push` over ssh går ikke derfra.
Push kjører du i et vanlig skall utenfor sandboxen — se [maskin-hardening](../sikkerhet/maskin-hardening/) for nøkkel- og signeringsoppsettet.

## Videre lesning

- [cplt](https://ki-utvikling.nav.no/cplt) og [navikt/cplt](https://github.com/navikt/cplt) — README, [SECURITY.md](https://github.com/navikt/cplt/blob/main/SECURITY.md) og [gh guard / git guard](https://ki-utvikling.nav.no/nyheter/cplt-gh-guard-git-guard)
- [github/copilot-cli](https://github.com/github/copilot-cli) og [installasjonsdokumentasjonen](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
- [Cloud and local sandboxes for GitHub Copilot](https://docs.github.com/en/copilot/how-tos/cloud-and-local-sandboxes) — status for den innebygde sandboxen, inkludert Windows
- [Microsoft: installere WSL](https://learn.microsoft.com/en-us/windows/wsl/install) og [kjerneutgivelser for WSL](https://learn.microsoft.com/en-us/windows/wsl/kernel-release-notes)
