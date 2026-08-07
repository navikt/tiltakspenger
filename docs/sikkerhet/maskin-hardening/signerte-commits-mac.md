# Signerte commits (macOS)

Commits på `main` skal signeres med en nøkkel som er bundet til utviklerens maskin og ikke kan kopieres ut av den.
Da er det maskinen, ikke en legitimasjon, som avgjør hva som kan lande på hovedgrenen: et token som kommer på avveie kan ikke produsere en gyldig signatur, uansett hvilke rettigheter det har.

Oppskriften bruker en nøkkel i Secure Enclave via [Secretive](https://github.com/maxgoedjen/secretive), som i tillegg krever fingeravtrykk per signatur.
Andre agenter som holder nøkkelen utenfor filsystemet fungerer likt — det som betyr noe er at den private nøkkelen aldri finnes som fil.
Secure Enclave lager bare ECDSA P-256-nøkler, så nøkkeltypen alene viser om en nøkkel er maskinvarebundet.

Oppskriften forutsetter at nøkkelen allerede finnes og er registrert — se [ssh-nokkel-mac.md](ssh-nokkel-mac.md).
På Linux, se [signerte-commits-linux.md](signerte-commits-linux.md).

## Oppsett

### 1. Legg den offentlige nøkkelen som fil

git trenger en fil å peke på, også når den private nøkkelen ligger i en agent.

```sh
SSH_AUTH_SOCK="$HOME/Library/Containers/com.maxgoedjen.Secretive.SecretAgent/Data/socket.ssh" \
  ssh-add -L > ~/.ssh/signeringsnokkel.pub
chmod 644 ~/.ssh/signeringsnokkel.pub
```

Holder agenten flere nøkler, plukk ut riktig linje før du lagrer.

### 2. Lag `allowed_signers`

Uten denne kan git signere, men ikke verifisere lokalt.

```sh
printf '%s %s\n' "$(git config user.email)" "$(cut -d' ' -f1,2 ~/.ssh/signeringsnokkel.pub)" \
  > ~/.ssh/allowed_signers
```

### 3. Pek `SSH_AUTH_SOCK` mot agenten

Dette er fella i hele oppsettet.
`IdentityAgent` i `~/.ssh/config` gjelder bare ssh-klienten, mens git signerer med `ssh-keygen -Y sign`, som utelukkende leser `SSH_AUTH_SOCK`.
Har du satt `IdentityAgent` og tror du er i mål, vil push virke mens signering feiler — og feilmeldingen peker ikke på årsaken.

```sh
export SSH_AUTH_SOCK="$HOME/Library/Containers/com.maxgoedjen.Secretive.SecretAgent/Data/socket.ssh"
```

Legg linja i shell-konfigen, ikke bare i det åpne vinduet.

### 4. Slå på signering i git

```sh
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/signeringsnokkel.pub
git config --global gpg.ssh.allowedSignersFile ~/.ssh/allowed_signers
git config --global commit.gpgsign true
```

### 5. Registrer nøkkelen som signeringsnøkkel på GitHub

<https://github.com/settings/ssh/new> med **Key type: Signing Key**.
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

`commit.gpgsign` er global, så kravet om fingeravtrykk gjelder hver commit i alle repoer på maskinen.
En rebase av ti commits blir ti bekreftelser.
