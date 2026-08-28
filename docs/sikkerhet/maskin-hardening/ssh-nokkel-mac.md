# SSH-nøkkel i Secure Enclave (macOS)

En nøkkelfil i `~/.ssh` kan kopieres — av deg, av et skript, eller av hva som helst som kjører som brukeren din.
En nøkkel i Secure Enclave kan ikke leses ut i det hele tatt, og kan i tillegg kreve fingeravtrykk hver gang den brukes.
Da er tilgangen bundet til maskinen og til at noen er til stede, ikke til en fil.

Samme nøkkel brukes til autentisering (clone, fetch, push) og til å signere commits.
Signeringen er dekket i [signerte-commits-mac.md](signerte-commits-mac.md) og forutsetter at du er ferdig her.

## 1. Installer Secretive

```sh
brew install --cask secretive
```

Alternativt hentes den fra <https://github.com/maxgoedjen/secretive/releases>.

Åpne appen første gang og la den installere **SecretAgent** som innloggingselement.
Det er den prosessen som svarer på ssh-forespørsler — uten den kjørende finnes ikke nøkkelen for ssh, og alt under vil feile.

## 2. Lag nøkkelen

I Secretive: **+** → gi nøkkelen et navn, gjerne maskinnavnet, så du kjenner den igjen på GitHub senere.

Hak av **Require authentication before use**.
Det er avkrysningen som gir fingeravtrykk per bruk, og dermed nærværskravet ved hver push og hver signatur.

Secure Enclave lager bare ECDSA P-256, så nøkkelen blir av typen `ecdsa-sha2-nistp256`.
Nøkkeltypen alene forteller altså om en nøkkel er maskinvarebundet.

Nøkkelen kan verken eksporteres eller sikkerhetskopieres — det er hele poenget.
Byttes maskinen, lager du en ny nøkkel, registrerer den, og sletter den gamle fra GitHub.

## 3. Pek ssh mot agenten

Legg dette i `~/.ssh/config`:

```
Host github.com
  IdentityAgent ~/Library/Containers/com.maxgoedjen.Secretive.SecretAgent/Data/socket.ssh
```

Secretive viser stien under **Setup** i appen.

Merk at `IdentityAgent` bare gjelder ssh-klienten.
Skal du også signere commits, må `SSH_AUTH_SOCK` i tillegg settes i shell-konfigen din (`~/.zshrc` eller tilsvarende) — det er steg 3 i [signerte-commits-mac.md](signerte-commits-mac.md).

## 4. Legg den offentlige nøkkelen på GitHub

Bruk **Copy Public Key** i Secretive, eller hent den fra agenten:

```sh
SSH_AUTH_SOCK="$HOME/Library/Containers/com.maxgoedjen.Secretive.SecretAgent/Data/socket.ssh" \
  ssh-add -L | pbcopy
```

Lim inn på <https://github.com/settings/ssh/new> med **Key type: Authentication Key**.

## 5. La git bruke ssh

```sh
gh config set git_protocol ssh
```

Skal push gå over ssh også i kloner som har HTTPS-URL, legg til i `~/.gitconfig`:

```
[url "git@github.com:"]
	pushInsteadOf = https://github.com/
```

`gh auth login` nullstiller `git_protocol` til `https`, så sjekk innstillingen etter hver ny innlogging.

## 6. Verifiser

```sh
ssh -T git@github.com
```

Fingeravtrykk-dialogen skal komme, og svaret skal være `Hi <brukernavn>! You've successfully authenticated`.
Kommer det ingen dialog, står nøkkelen uten **Require authentication before use**.
Kommer det «Permission denied», svarer ikke SecretAgent — sjekk at den kjører og at stien i `~/.ssh/config` stemmer.

## 7. Rydd bort nøkler som ikke er maskinvarebundet

En registrert nøkkel med privatdelen liggende som fil er en parallell vei inn, og den er ikke beskyttet av Enclave-en.
Så lenge en slik nøkkel står på kontoen, gjelder ikke nærværskravet i praksis — den som har fila kan bruke den uten fingeravtrykk.

Gå gjennom <https://github.com/settings/keys>, se på «Last used», og slett nøkler du ikke kan plassere.
Nøkkeltypen er et godt hint: `ssh-ed25519` og `ssh-rsa` er alltid programvarenøkler, mens `ecdsa-sha2-nistp256` kan være Enclave-bundet.

Listen er offentlig, så den kan sjekkes uten innlogging:

```sh
curl -s https://api.github.com/users/<brukernavn>/keys
```
