"""Filtyper, kommentarhåndtering og skillet mellom prod- og testkode.

Samler den språkavhengige logikken for Kotlin, TypeScript, Rust, Terraform,
YAML, shell og Python, slik at sjekkene betyr det samme på tvers.
"""
import re

# --- Filtyper ----------------------------------------------------------------

# Filer nettverkssjekken ser på. Markdown er utenfor fordi en URL der er en
# lenke, ikke et kall.
KODEFILER = {
    ".kt", ".kts", ".java",              # JVM
    ".ts", ".tsx", ".js", ".mjs", ".cjs", ".astro",  # frontend
    ".rs",                               # rust
    ".py", ".sh",                        # skript
    ".yml", ".yaml", ".tf", ".hcl", ".toml",  # konfig og infrastruktur
}

# Språkfamilier for prosess-sjekken. En familie deler både mønstre og syntaks.
JVM_FILER = {".kt", ".kts", ".java"}
RUST_FILER = {".rs"}
NODE_FILER = {".ts", ".tsx", ".js", ".mjs", ".cjs", ".astro"}
PYTHON_FILER = {".py"}

# --- Kommentarer -------------------------------------------------------------

# Kommentarmerker og strengtegn per familie.
#
# I Kotlin, Java og Rust er «'» tegnliteral eller apostrof, ikke
# strengavgrenser. Å telle den ville gjort «"don't"» til en uavsluttet streng,
# slik at en etterfølgende kommentar aldri ble klippet.
#
# I JavaScript og TypeScript avgrenser både «'» og backtick strenger, og de må
# telles: uten «'» ville «const x = '//';» kuttet resten av linja, og et
# nettverks- eller prosesskall etter den blitt usynlig. Prisen er at en
# apostrof inne i en dobbeltsitert streng kan hindre klipping av en
# etterfølgende kommentar — et falskt treff veier lettere enn et tapt.
JVM_OG_RUST = {".kt", ".kts", ".java", ".rs"}
JS_FAMILIE = {".ts", ".tsx", ".js", ".mjs", ".cjs", ".astro"}
HASH_SPRÅK = {".sh", ".py", ".yml", ".yaml", ".properties", ".toml"}
# Terraform og HCL støtter både «#» og «//».
BEGGE_KOMMENTARTYPER = {".tf", ".hcl"}
# SQL: «--» til linjeslutt, og «/* … */». Migrasjoner ligger under src/main og er prod.
SQL_FILER = {".sql"}


def kommentarsyntaks(endelse):
    """Returnerer (kommentarmerker, strengtegn) for filtypen, eller None."""
    if endelse in JVM_OG_RUST:
        return ("//",), ('"',)
    if endelse in JS_FAMILIE:
        return ("//",), ('"', "'", "`")
    if endelse in HASH_SPRÅK:
        return ("#",), ('"', "'")
    if endelse in BEGGE_KOMMENTARTYPER:
        return ("#", "//"), ('"',)
    if endelse in SQL_FILER:
        return ("--",), ("'",)
    return None


# Filer som er dokumentasjon, ikke kode. Nettverkssjekken hopper over dem via
# KODEFILER; for fnr-sjekken betyr de at et uvalidert ellevesiffer ikke er funn.
DOKUMENTFILER = {".md", ".markdown", ".mdx"}

# Språk med blokkommentarer «/* … */» i tillegg til linjekommentaren.
BLOKKOMMENTAR_SPRÅK = JVM_OG_RUST | JS_FAMILIE | BEGGE_KOMMENTARTYPER | SQL_FILER


def er_kommentarlinje(linje, endelse=None):
    """Sant når hele linja er en kommentar.

    «/* … */ kode» er ikke en kommentarlinje: blokka lukkes, og koden etter
    den kjører. Da klipper uten_kommentar bort blokka og beholder koden.
    «--» teller bare i SQL: i et shellskript er «--flagg» på egen linje kode.
    """
    renset = linje.lstrip()
    if renset.startswith("/*"):
        slutt = renset.find("*/")
        return slutt == -1 or not renset[slutt + 2:].strip()
    if endelse in SQL_FILER and renset.startswith("--"):
        return True
    return renset.startswith(("//", "#", "*", "<!--"))


def uten_blokkommentar(linje, strengtegn):
    """Fjerner «/* … */» som åpner på linja, utenfor strenger.

    Returnerer (resten av linja, om en blokk står åpen ved linjeslutt). Lukkes
    blokka på samme linje, tas bare spennet ut og koden rundt beholdes. Lukkes
    den ikke, er resten av linja kommentar, og kodetekst() fortsetter blokka
    på neste linje.
    """
    while True:
        i = linje.find("/*")
        if i == -1:
            return linje, False
        if any(linje.count(tegn, 0, i) % 2 for tegn in strengtegn):
            return linje, False  # inne i en streng: ikke en kommentar
        j = linje.find("*/", i + 2)
        if j == -1:
            return linje[:i], True
        linje = linje[:i] + " " + linje[j + 2:]


def uten_kommentar(linje, endelse):
    """Klipper vekk kommentarene på linja: «/* … */» og en etterfølgende linjekommentar.

    En URL eller et prosesskall i en kommentar er dokumentasjon, ikke kode.
    «//» inne i en URL har alltid «:» foran seg, og en kommentarstart inne i en
    streng har et odde antall anførselstegn foran seg — begge deler holder
    klippingen unna kode.
    """
    kode, _ = _uten_kommentar(linje, endelse)
    return kode


def kodetekst(linjer, endelse):
    """Koden i hver linje, med kommentarene klippet bort — tom streng for rene
    kommentarlinjer. Følger «/* … */» over flere linjer, så en dokumentasjonslenke
    på linje to i en blokk uten innledende «*» ikke leses som et kall. Én
    beregning per fil, delt av nettverk, prosess og fnr.
    """
    ut = []
    i_blokk = False
    for linje in linjer:
        if i_blokk:
            j = linje.find("*/")
            if j == -1:
                ut.append("")
                continue
            linje = linje[j + 2:]
            i_blokk = False
        if er_kommentarlinje(linje, endelse):
            if endelse in BLOKKOMMENTAR_SPRÅK and linje.lstrip().startswith("/*") \
                    and "*/" not in linje:
                i_blokk = True
            ut.append("")
            continue
        kode, i_blokk = _uten_kommentar(linje, endelse)
        ut.append(kode)
    return ut


def _uten_kommentar(linje, endelse):
    """(kode, blokk åpen ved linjeslutt)."""
    syntaks = kommentarsyntaks(endelse)
    if syntaks is None:
        return linje, False
    merker, strengtegn = syntaks
    åpen = False
    if endelse in BLOKKOMMENTAR_SPRÅK:
        linje, åpen = uten_blokkommentar(linje, strengtegn)
    for i in range(len(linje)):
        for merke in merker:
            if not linje.startswith(merke, i):
                continue
            if merke == "//" and i > 0 and linje[i - 1] == ":":
                continue
            if any(linje.count(tegn, 0, i) % 2 for tegn in strengtegn):
                continue
            return linje[:i], åpen
    return linje, åpen


# --- Produksjonskode eller testkode ------------------------------------------

# Stier som er testkode. Alt annet er prod — også Nais-manifester, Terraform,
# konfig, skript og byggfiler. Lista er ment å utvides: legg til et mønster her
# når et repo har en testkatalog vi ikke har sett før.
TESTSTI_MØNSTRE = (
    # JVM: kildesett og testfixturer.
    re.compile(r"(^|/)src/(test|testFixtures)/"),
    # Testkatalog i rota, som i Rust. Ankeret «^» hindrer treff på Kotlin-pakker
    # som heter «test» under src/main.
    re.compile(r"^tests?/"),
    # Frontend: filnavn og kataloger.
    # Uten ende-anker, slik at «foo.test.d.ts» og «foo.spec.ts.snap» også
    # regnes som test. «.stories.» hører til av samme grunn som «.spec.»:
    # Storybook-filer kjører i katalogen, aldri i det som deployes.
    re.compile(r"\.(test|spec|stories)\."),
    re.compile(r"(^|/)(__tests__|e2e|playwright|fixtures|testdata|test-data)/"),
    # Testriggenes egen konfigurasjon. Kun kjørerne — bygg- og lintconfiger
    # (vite, next, astro, eslint) blir med i deployment og er prod.
    # cypress.config hører til kjørerne av samme grunn som playwright.config.
    re.compile(r"(^|/)(playwright|vitest|jest|cypress)\.config\.[A-Za-z0-9]+$"),
    # Compose-oppsett kjører lokalt og på utviklermaskiner. Nais deployer kun
    # via manifester, så en compose-fil følger aldri med noe sted.
    re.compile(r"(^|/)(docker-)?compose[^/]*\.(yml|yaml)$"),
    # Maler og testoppsett for miljøvariabler. Merk at kun mal- og
    # test-suffiksene er med: .env.prod, .env.dev og .env.demo er ekte
    # byggkonfigurasjon, og NEXT_PUBLIC_-verdiene der bakes inn i bundelen
    # som skipes. En ren .env er usporet og leses aldri uansett.
    re.compile(r"(^|/)\.env[-.](template|example|sample|dist|tests?)$"),
    # Metarepoets WireMock-svar for lokal kjøring.
    re.compile(r"^mock-req-res/"),
)

# Moduler som bare er testinfrastruktur, selv om koden ligger under «src/main».
# Mønstrene er avstemt mot modulnavnene i libs.
TESTMODUL_MØNSTRE = (
    re.compile(r"(^|/)[a-z0-9-]*test-common(/|$)"),
    re.compile(r"(^|/)[a-z0-9-]+-test(/|$)"),
    re.compile(r"(^|/)[a-z0-9-]+-test-core(/|$)"),
)


def er_testfil(sti):
    """Sant når fila er testkode. Alt annet regnes som produksjonskode.

    Begrensning: en Rust-fil med `#[cfg(test)]`-modul under `src/` regnes som
    prod, fordi skriptet ikke skiller på blokknivå.
    """
    if any(mønster.search(sti) for mønster in TESTSTI_MØNSTRE):
        return True
    return any(mønster.search(sti) for mønster in TESTMODUL_MØNSTRE)


def scope(sti):
    """«test» eller «prod» — navnet på unntakslista som gjelder for fila."""
    return "test" if er_testfil(sti) else "prod"
