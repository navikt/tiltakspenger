# Maskin-hardening

Oppskrifter for å herde utviklermaskinen.
Fellesnevneren er at nøkler og hemmeligheter skal ligge i maskinvare og kreve at et menneske er til stede, framfor å ligge som filer en prosess kan lese — og at legitimasjon som er tilgjengelig hele tiden bare skal kunne lese.

De to første hører sammen og tas i rekkefølge, siden signering forutsetter at nøkkelen finnes.

1. [SSH-nøkkel i Secure Enclave (macOS)](ssh-nokkel-mac.md) — Secretive, nøkkelgenerering og registrering på GitHub. Testet.
2. [Signerte commits (macOS)](signerte-commits-mac.md) — signering med samme nøkkel, og hvordan kravet slås på i et repo. Testet.
3. [Lesetoken for `gh`](gh-lesetoken.md) — fine-grained token uten skrivetilgang, i stedet for OAuth-grantet `gh auth login` lager. Testet.

For Linux dekker [signerte commits (Linux)](signerte-commits-linux.md) både nøkkelgenerering med FIDO2-sikkerhetsnøkkel og signering i én oppskrift.
Den er **ikke testet**.
Punkt 3 er plattformuavhengig utover at `pbpaste` og `pbcopy` er macOS-kommandoer.
