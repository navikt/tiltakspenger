# Signerte commits (Linux)

> **Ikke testet.** Oppskriften er utledet fra hvordan FIDO2-nøkler og git-signering fungerer, ikke fra en gjennomkjøring.
> Rett opp det som avviker når du følger den, og fjern denne boksen når hele veien er bekreftet — inkludert at GitHub svarer `"verified": true`.

Commits på `main` skal signeres med en nøkkel som er bundet til maskinvare og ikke kan kopieres.
Da er det maskinvaren, ikke en legitimasjon, som avgjør hva som kan lande på hovedgrenen: et token som kommer på avveie kan ikke produsere en gyldig signatur, uansett hvilke rettigheter det har.

Linux har ingen Secure Enclave.
Det nærmeste tilsvarende er en **FIDO2-sikkerhetsnøkkel** — den private nøkkelen bor i maskinvaren, og fila på disk er bare et håndtak som er verdiløst uten at nøkkelen er plugget i.
På macOS brukes Secure Enclave i stedet, se [signerte-commits-mac.md](signerte-commits-mac.md).

Forutsetter OpenSSH 8.3 eller nyere og git 2.34 eller nyere.

## Oppsett

### 1. Lag en maskinvarebundet nøkkel

```sh
ssh-keygen -t ed25519-sk -O resident -O verify-required \
  -C "$(git config user.email)" -f ~/.ssh/signeringsnokkel
```

- `-O verify-required` krever PIN i tillegg til berøring ved hver signatur. Det er denne som gir nærværskontrollen.
- `-O resident` lagrer nøkkelen på selve sikkerhetsnøkkelen, så den kan hentes ned igjen på en ny maskin med `ssh-keygen -K`. Uten den mister du nøkkelen om `~/.ssh`-fila forsvinner.
- Svarer tokenet at `ed25519-sk` ikke støttes, bruk `-t ecdsa-sk` i stedet. Eldre nøkler støtter ofte bare den.

Kommandoen lager `~/.ssh/signeringsnokkel` (håndtaket) og `~/.ssh/signeringsnokkel.pub`.

### 2. Lag `allowed_signers`

Uten denne kan git signere, men ikke verifisere lokalt.

```sh
printf '%s %s\n' "$(git config user.email)" "$(cut -d' ' -f1,2 ~/.ssh/signeringsnokkel.pub)" \
  > ~/.ssh/allowed_signers
```

### 3. Slå på signering i git

```sh
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/signeringsnokkel
git config --global gpg.ssh.allowedSignersFile ~/.ssh/allowed_signers
git config --global commit.gpgsign true
```

Merk at `user.signingkey` her peker på **håndtaket**, ikke på `.pub`-fila.
Da går signeringen rett mot sikkerhetsnøkkelen uten agent.
Bruker du i stedet en `ssh-agent` som holder nøkkelen, pek på `.pub`-fila — og pass da på at `SSH_AUTH_SOCK` er satt i shell-konfigen, siden `ssh-keygen -Y sign` ikke leser `IdentityAgent` fra `~/.ssh/config`.

### 4. Registrer nøkkelen som signeringsnøkkel på GitHub

<https://github.com/settings/ssh/new> med **Key type: Signing Key**, og innholdet fra `~/.ssh/signeringsnokkel.pub`.
Signeringsnøkler er en egen liste — at nøkkelen allerede ligger der som autentiseringsnøkkel teller ikke.

## Verifiser før kravet slås på

Test på en gren, aldri på `main`: i repoer med en `deploy-prod.yml` trigger push til `main` en utrulling.

```sh
git switch -c test/signering
git commit --allow-empty -m 'Verifiser signering'
git log -1 --format='%h %G? %GS'
```

`G` betyr god signatur.
`N` betyr usignert, mens `U` eller `E` betyr signert uten at den lot seg verifisere mot `allowed_signers`.

Push så grenen og sjekk at GitHub godtar signaturen serverside:

```sh
git push -u origin test/signering
gh api repos/navikt/<repo>/commits/$(git rev-parse HEAD) --jq .commit.verification
```

Forventet er `"verified": true` med `"reason": "valid"`.
Rydd opp etterpå:

```sh
git switch main && git branch -D test/signering && git push origin --delete test/signering
```

## Slå på kravet i et repo

Grenbeskyttelse i GitHub finnes i to uavhengige systemer, og kravet kan slås på i begge.
Sjekk hva repoet allerede har før du lager noe nytt: **Settings → Branches** viser klassiske regler, **Settings → Rules → Rulesets** viser rulesets.
Merk at API-et `repos/{repo}/rules/branches/main` bare returnerer rulesets — et repo kan ha klassisk beskyttelse selv om det svarer tomt.

Har repoet allerede en klassisk regel for `main`, er det ett klikk: hak av **Require signed commits** og lagre nederst på siden.

Ellers lag en ruleset — **Settings → Rules → Rulesets → New branch ruleset**:

- Enforcement status: `Active`
- Target branches: Include default branch
- Branch rules: `Require signed commits`

Uansett vei: la bypass-lista stå tom.
Legges kontoer inn der, er regelen dekorativ — det er nettopp en utviklerkonto et lekket token opptrer som.

## Dependabot og CI

Commits GitHub lager selv gjennom API-et er GitHub-signert og passerer kravet.
Det gjelder både dependabots egne commits og merge-commitene auto-merge-workflowen lager med `GITHUB_TOKEN`.

En workflow som derimot kjører `git push` med `GITHUB_TOKEN` lager usignerte commits, og de vil bli avvist.
Sjekk at repoet ikke har en slik jobb før du slår på kravet.

## Praktiske konsekvenser

`commit.gpgsign` er global, så PIN og berøring kreves for hver commit i alle repoer på maskinen.
En rebase av ti commits blir ti bekreftelser.
Sikkerhetsnøkkelen må være plugget i for at du skal kunne committe i det hele tatt.
