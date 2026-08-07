# Maskin-hardening

Oppskrifter for å herde utviklermaskinen.
Fellesnevneren er at nøkler og hemmeligheter skal ligge i maskinvare og kreve at et menneske er til stede, framfor å ligge som filer en prosess kan lese.

Ta dem i rekkefølge — signering forutsetter at nøkkelen finnes.

1. [SSH-nøkkel i Secure Enclave (macOS)](ssh-nokkel-mac.md) — Secretive, nøkkelgenerering og registrering på GitHub. Testet.
2. [Signerte commits (macOS)](signerte-commits-mac.md) — signering med samme nøkkel, og hvordan kravet slås på i et repo. Testet.

For Linux dekker [signerte commits (Linux)](signerte-commits-linux.md) både nøkkelgenerering med FIDO2-sikkerhetsnøkkel og signering i én oppskrift.
Den er **ikke testet**.
