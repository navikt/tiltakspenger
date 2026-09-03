"""Eksterne verktøy skanneren kaller ut til.

Mønsteret er likt for alle: finn binæren på PATH, kjør den mot målrepoet, og
oversett resultatet til vår vanlige treff-form. Mangler binæren, hopper sjekken
over med beskjed — den skal aldri velte en kjøring, og aldri forsvinne stille.

Hemmeligheter kommer aldri ut herfra. Verktøyene kjøres med redaksjon påslått,
og vi plukker kun regel-id, sted og commit ut av rapporten.
"""
import json
import os
import shutil
import subprocess
import tempfile


def finn(binærnavn):
    """Stien til verktøyet, eller None om det ikke ligger på PATH."""
    return shutil.which(binærnavn)


def versjon(binær):
    """Versjonsstrengen verktøyet oppgir, til bevis-headeren."""
    try:
        resultat = subprocess.run([binær, "version"], capture_output=True,
                                  text=True, check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "ukjent versjon"
    tekst = (resultat.stdout or resultat.stderr).strip().splitlines()
    return f"{tekst[0].strip()} ({binær})" if tekst else f"ukjent versjon ({binær})"


def kjør_gitleaks(repo, binær=None):
    """Kjører gitleaks over hele git-historikken i repoet.

    Returnerer (treff, feilmelding). Feilmelding er None når kjøringen gikk
    som den skulle — også når den fant noe, siden funn er hele poenget.

    `--redact` gjør at hemmeligheten aldri havner i rapporten. Vi leser
    dessuten bare regel-id, fil, linje og commit ut av den, og lar
    `Secret`- og `Match`-feltene ligge urørt uansett hva de måtte inneholde.
    """
    binær = binær or finn("gitleaks")
    if binær is None:
        return [], "gitleaks ikke på PATH"

    with tempfile.TemporaryDirectory() as tmp:
        rapport = os.path.join(tmp, "gitleaks.json")
        resultat = subprocess.run(
            [binær, "git", "--redact", "--exit-code", "1",
             "--report-format", "json", "--report-path", rapport, repo],
            capture_output=True, text=True,
        )
        # 0 = ingen funn, 1 = funn. Alt annet er en ekte feil.
        if resultat.returncode not in (0, 1):
            kort = (resultat.stderr or resultat.stdout).strip().splitlines()
            return [], f"gitleaks feilet (exit {resultat.returncode}): " + (
                kort[-1] if kort else "ingen utskrift")
        if not os.path.isfile(rapport):
            return [], None
        try:
            with open(rapport, encoding="utf-8") as fh:
                rådata = json.load(fh) or []
        except (OSError, ValueError) as årsak:
            return [], f"kunne ikke lese gitleaks-rapporten: {årsak}"

    treff = []
    for post in rådata:
        regel = post.get("RuleID") or "ukjent regel"
        sti = post.get("File") or "(ukjent fil)"
        linje = post.get("StartLine") or 0
        commit = (post.get("Commit") or "")[:7]
        dato = (post.get("Date") or "")[:10]
        beskrivelse = post.get("Description") or ""
        hvor = f"commit {commit}" if commit else "arbeidskopien"
        if dato:
            hvor += f" {dato}"
        melding = f"{regel} i {hvor}"
        if beskrivelse and beskrivelse.lower() != regel.lower():
            melding += f" — {beskrivelse}"
        # Matchteksten er regel-id-en, aldri verdien: den skrives ut i
        # funnlinja, og en hemmelighet skal ikke kunne havne der.
        treff.append(("gitleaks", "FUNN", sti, linje, melding, regel))
    return treff, None
