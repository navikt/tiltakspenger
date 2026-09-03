"""Sjekkreglene. Hver av dem legger treff på en felles liste.

Et treff er (sjekk, nivå, sti, linjenr, melding, matchtekst). Nivå er «FUNN»
eller «INFO»; INFO-treff vises kun med --info og gir aldri exit 1.
"""
import ipaddress
import re

from . import siffer, spraak

# «gitleaks» er en ekstern sjekk: den kjører ikke per fil som de andre, men
# sheller ut til gitleaks-binæren én gang per repo. Se skannlib/verktoy.py.
SJEKKER = ("nettverk", "prosess", "hemmeligheter", "jwt", "base64", "fnr",
           "kontonummer", "gitleaks")

# --- Godkjente verter --------------------------------------------------------
#
# Godkjenningen er scope-avhengig, etter samme skille som 11-sifferregelen.
# Prinsippet er hva som blir med i deployment: testkode er kode som ikke gjør
# det. En config-default i src/main blir med i artefakten og er derfor prodkode
# fullt ut, selv om verdien bare brukes lokalt.
#
# I test er lista romslig — en testfixtur skal kunne peke på hva som helst
# fiktivt. I prod er den minimal: kun våre egne domener.

# Verter som er greie i TESTKODE: lokal utvikling og dokumentasjon.
GODKJENTE_TESTVERTER = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "host.docker.internal",
    "example.com",
    "example.org",
    "example.net",
    # RFC 5737 — adresser reservert for dokumentasjon.
    "192.0.2.1",
    "198.51.100.1",
    "203.0.113.1",
}

# Suffikser som er greie i TESTKODE: reservert til test og lokal bruk (RFC
# 6761, RFC 2606), pluss våre egne. Både apex-domenet og underdomener
# godkjennes.
GODKJENTE_TESTSUFFIKSER = (
    ".test", ".local", ".localhost", ".invalid", ".example",
    ".example.com", ".example.org", ".example.net",
    ".nav.no", ".adeo.no", ".nais.io",
)

# Det eneste som er godkjent i PRODUKSJONSKODE: våre egne domener. Alt annet
# er et funn — også localhost, 127.0.0.1, 0.0.0.0, ::1 og
# host.docker.internal. En lokal adresse i kode som blir med er en
# lokal-profildefault på avveie, ikke noe skriptet skal tie om.
#
# «.local» står bevisst ikke her. Målt i flåten 2026-09-02 finnes elector.local
# (Nais leader elector) og texas.local kun i testkode — 13 forekomster, alle
# under src/test. Dukker ekte prodbruk opp, hører den hjemme som en begrunnet
# unntaksoppføring, ikke som en oppmyking av lista.
GODKJENTE_PRODSUFFIKSER = (".nav.no", ".adeo.no", ".nais.io")

# Egne apper adressert med tjenestenavn i klyngen («http://tiltakspenger-tiltak»
# og den namespace-kvalifiserte «http://tiltakspenger-x.tpts»). Dette er Nais'
# service discovery i vårt eget namespace, og den eneste verten uten et av våre
# domenesuffikser som er godkjent i prod.
#
# Begge ledd er bundet: appnavnet må ha tiltakspenger-prefikset, og namespacet
# må være tpts. Et tjenestenavn i et annet team sitt namespace er et kall ut av
# tillitsdomenet vårt og skal fortsatt være et funn.
#
# Målt i flåten 2026-09-02: fem enkeltledds-navn i prodkode, alle med
# tiltakspenger-prefikset, ingen legitime utenfor det — og én kvalifisert form,
# tiltakspenger-meldekort-microfrontend.tpts.
K8S_TJENESTE = re.compile(r"^tiltakspenger-[a-z0-9-]+(\.tpts)?$")

# Klammet IPv6-vert («http://[::1]:8080») fanges for seg: «]» må med i verten,
# men ikke ellers — der avslutter den en liste eller en Markdown-lenke.
URL_MØNSTER = re.compile(
    r"\b(?:https?|wss?)://(\[[0-9A-Fa-f:.]+\](?::\d+)?|[^\s\"'`<>,\)\]\}\\]+)",
    re.IGNORECASE,
)

# --- Prosess og sockets ------------------------------------------------------
#
# Mønstrene er valgt for signal framfor bredde. `exec(` og `spawn(` alene er
# utelatt: `regex.exec(...)` er dagligdags i JavaScript og ville druknet de
# ekte funnene. Derfor kreves enten `child_process`-konteksten eller de
# synkrone variantene, som ikke finnes andre steder.
PROSESS_MØNSTRE = {
    "jvm": [
        (re.compile(r"Runtime\.getRuntime\(\)\s*\.\s*exec"),
         "starter prosess med Runtime.exec"),
        (re.compile(r"\bProcessBuilder\b"), "starter prosess med ProcessBuilder"),
        (re.compile(r"\bjava\.net\.(?:Socket|DatagramSocket|ServerSocket)\b"),
         "åpner rå socket"),
        (re.compile(r"(?<![\w.])(?:Socket|DatagramSocket|ServerSocket)\("),
         "åpner rå socket"),
        (re.compile(r"System\.loadLibrary"), "laster native bibliotek"),
    ],
    "rust": [
        (re.compile(r"std::process::Command|\bCommand::new\b"),
         "starter prosess med std::process::Command"),
        (re.compile(r"\b(?:TcpStream|TcpListener|UdpSocket|UnixStream)::"),
         "åpner rå socket"),
        (re.compile(r"\blibloading\b|\bdlopen\b"), "laster native bibliotek"),
    ],
    "node": [
        (re.compile(r"""["']child_process["']|\bchild_process\."""),
         "starter prosess via child_process"),
        # Gruppa blander synkrone og asynkrone kall — execFile er asynkron —
        # så meldingen sier ikke noe om hvilken av delene.
        (re.compile(r"\b(?:execSync|execFileSync|spawnSync|execFile)\s*\("),
         "starter prosess med exec- eller spawn-kall"),
        (re.compile(r"\bnet\.(?:Socket|createConnection|createServer)\b|\bdgram\."),
         "åpner rå socket"),
    ],
    "python": [
        # Navngitte kall, ikke bare «subprocess.»: et unntaksfilter som fanger
        # subprocess.CalledProcessError starter ingen prosess.
        (re.compile(r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\b"
                    r"|\bos\.(?:system|popen|exec[lv])\b"),
         "starter prosess"),
        (re.compile(r"\bsocket\.socket\b|\bsocketserver\b"), "åpner rå socket"),
        (re.compile(r"\bctypes\.(?:CDLL|WinDLL)\b"), "laster native bibliotek"),
    ],
}


def prosessfamilie(endelse):
    if endelse in spraak.JVM_FILER:
        return "jvm"
    if endelse in spraak.RUST_FILER:
        return "rust"
    if endelse in spraak.NODE_FILER:
        return "node"
    if endelse in spraak.PYTHON_FILER:
        return "python"
    return None


# --- Hemmeligheter -----------------------------------------------------------

HEMMELIGHET_MØNSTRE = [
    (re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
     "privat nøkkel i klartekst"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}"), "GitHub personal access token"),
    (re.compile(r"\bgho_[A-Za-z0-9]{20,}"), "GitHub OAuth-token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "Slack-token"),
]

MILJØ_HEMMELIGHET = re.compile(
    r"\b((?:NAIS|AZURE)_[A-Z0-9_]{2,})\s*[=:]\s*[\"']?([A-Za-z0-9._~+/=-]{20,})[\"']?",
)
PLASSHOLDER = re.compile(
    r"^(?:\$|<|\{)|(?:changeme|placeholder|dummy|xxxx|todo|secret_here|hemmelighet)",
    re.IGNORECASE,
)
# Verdier som er navn, ikke hemmeligheter: små bokstaver i ledd skilt av
# bindestrek eller punktum, uten entropi. En GUID starter med et siffer eller
# blander store og små bokstaver, og fanges fortsatt.
NAVNEFORM = re.compile(r"^[a-z][a-z0-9]*(?:[-.][a-z0-9]+)*$")

JWT_MØNSTER = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}")

# --- Base64 ------------------------------------------------------------------

BASE64_MØNSTER = re.compile(r"[A-Za-z0-9+/]{60,}={0,2}")
BARE_HEKS = re.compile(r"^(?:[0-9a-f]+|[0-9A-F]+)$")
# «/» er et base64-tegn, så en filsti av rene ordledd treffer mønsteret.
STIFORM = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:/[A-Za-z][A-Za-z0-9]*){2,}$")
BASE64_UNNTAK = re.compile(
    r"(^|/)("
    r"[^/]*\.lock|[^/]*-lock\.json|[^/]*\.min\.(js|css)|[^/]*\.svg|"
    r"[^/]*\.(png|jpg|jpeg|gif|ico|pdf|woff2?|ttf)|"
    r"gradle/verification-metadata\.xml"
    r")$",
)


# --- Sjekkene ----------------------------------------------------------------

def vert_er_godkjent(vert, scope):
    """Om verten er godkjent i dette scopet («prod» eller «test»)."""
    vert = vert.lower().split("@")[-1]
    if vert.startswith("[") and "]" in vert:
        # Klammet IPv6-vert: klammene bærer adressen, porten står etter dem.
        vert = vert[1:vert.index("]")]
    elif ":" in vert:
        # Kun portavkorting. En uklammet IPv6-adresse har kolon i seg selv, og
        # ville blitt kuttet til tom streng — da beholder vi hele verten.
        vert = vert.split(":")[0] or vert
    vert = vert.rstrip(".")

    # Den første vakten er strukturell, ikke en godkjenning: den sier at
    # strengen ikke er en adresse vi kan vurdere, og gjelder i begge scope.
    if not vert or "$" in vert or "{" in vert or "%" in vert:
        return True  # interpolert vert, ikke en adresse

    if scope == "prod":
        # Enkeltledds verter godkjennes ikke her. En teststubb som
        # «http://test» hører ikke hjemme i kode som blir med i artefakten, og
        # «localhost» er en lokal-profildefault på avveie. Unntaket er våre egne
        # apper adressert på tjenestenavn i klyngen.
        if K8S_TJENESTE.match(vert):
            return True
        return any(vert == suffiks.lstrip(".") or vert.endswith(suffiks)
                   for suffiks in GODKJENTE_PRODSUFFIKSER)

    if "." not in vert and not _er_ip(vert):
        # Enkeltledds vert kan ikke slås opp utenfor et lokalt søkedomene. I
        # testkode er det en stubb («http://test», «http://pdl»), ikke et kall.
        return True
    if vert in GODKJENTE_TESTVERTER:
        return True
    try:
        adresse = ipaddress.ip_address(vert)
    except ValueError:
        pass
    else:
        # En IP-adresse avgjøres av adresserommet, ikke av navnereglene under.
        return adresse.is_loopback or adresse.is_private or adresse.is_unspecified
    return any(vert == suffiks.lstrip(".") or vert.endswith(suffiks)
               for suffiks in GODKJENTE_TESTSUFFIKSER)


def _er_ip(vert):
    try:
        ipaddress.ip_address(vert)
    except ValueError:
        return False
    return True


def nettverk(sti, endelse, linjer, treff):
    if endelse not in spraak.KODEFILER:
        return
    scope = spraak.scope(sti)
    for nr, linje in enumerate(linjer, 1):
        if spraak.er_kommentarlinje(linje):
            continue
        kode = spraak.uten_kommentar(linje, endelse)
        for match in URL_MØNSTER.finditer(kode):
            vert = match.group(1).split("/")[0]
            if vert_er_godkjent(vert, scope):
                continue
            treff.append(("nettverk", "FUNN", sti, nr,
                          f"ikke-godkjent vert i {scope}: {vert}", match.group(0)))


def prosess(sti, endelse, linjer, treff):
    familie = prosessfamilie(endelse)
    if familie is None:
        return
    for nr, linje in enumerate(linjer, 1):
        if spraak.er_kommentarlinje(linje):
            continue
        kode = spraak.uten_kommentar(linje, endelse)
        for mønster, melding in PROSESS_MØNSTRE[familie]:
            if mønster.search(kode):
                treff.append(("prosess", "FUNN", sti, nr, melding, kode))
                break


def hemmeligheter(sti, linjer, treff):
    for nr, linje in enumerate(linjer, 1):
        for mønster, melding in HEMMELIGHET_MØNSTRE:
            match = mønster.search(linje)
            if match:
                treff.append(("hemmeligheter", "FUNN", sti, nr, melding,
                              match.group(0)))
        match = MILJØ_HEMMELIGHET.search(linje)
        if (match
                and not PLASSHOLDER.search(match.group(2))
                and not NAVNEFORM.match(match.group(2))):
            treff.append(("hemmeligheter", "FUNN", sti, nr,
                          f"{match.group(1)} satt til en lang literal",
                          match.group(0)))


def jwt(sti, linjer, treff):
    for nr, linje in enumerate(linjer, 1):
        for match in JWT_MØNSTER.finditer(linje):
            treff.append(("jwt", "FUNN", sti, nr, "JWT-lignende streng",
                          match.group(0)))


def base64(sti, linjer, treff):
    if BASE64_UNNTAK.search(sti):
        return
    for nr, linje in enumerate(linjer, 1):
        for match in BASE64_MØNSTER.finditer(linje):
            tekst = match.group(0)
            if BARE_HEKS.match(tekst):
                continue  # sjekksum eller hash
            if not (any(c.islower() for c in tekst)
                    and any(c.isupper() for c in tekst)
                    and any(c.isdigit() for c in tekst)):
                continue  # mangler tegnvariasjonen ekte base64 alltid har
            if STIFORM.match(tekst):
                continue  # filsti
            før = linje[match.start() - 1] if match.start() else ""
            etter = linje[match.end()] if match.end() < len(linje) else ""
            if før in "./-_" or etter in "./-_":
                continue  # midt i en lengre sti eller identifikator
            treff.append(("base64", "FUNN", sti, nr,
                          f"base64-literal på {len(tekst)} tegn", tekst))


def prod_melding(tekst):
    """Bygger meldingen for et 11-sifret tall i produksjonskode.

    Funnet er at tallet står der. Validerer det i tillegg som fnr eller
    kontonummer, sier meldingen det — da er alvoret høyere.
    """
    kategori = siffer.fnr_kategori(tekst)
    if kategori is not None:
        return f"11 siffer i produksjonskode — {kategori[1]}"
    if siffer.er_gyldig_konto(tekst):
        return "11 siffer i produksjonskode — validerer som kontonummer"
    return "11 siffer i produksjonskode"


def fnr(sti, linjer, treff):
    """11-sifrede tall. Strengere i prod enn i test.

    I produksjonskode er ethvert frittstående 11-sifret tall et funn: det finnes
    ingen god grunn til å skrive et der, og en mod11-sjekk ville sluppet gjennom
    både avkortede identer og tall som blir gyldige etter en tastefeil. Kun
    kontekstvaktene gjelder, og de skiller ut det som ikke er et frittstående
    tall.

    I testkode valideres tallet mot begge ordningene, og syntetiske serier
    rapporteres som INFO.
    """
    prod = not spraak.er_testfil(sti)
    for nr, linje in enumerate(linjer, 1):
        for match in siffer.FNR_MØNSTER.finditer(linje):
            if siffer.del_av_lengre_verdi(linje, match.start(), match.end()):
                continue
            tekst = match.group(0)
            if prod:
                treff.append(("fnr", "FUNN", sti, nr, prod_melding(tekst), tekst))
                continue
            if siffer.er_plassholdersekvens(tekst):
                continue
            kategori = siffer.fnr_kategori(tekst)
            if kategori is None:
                continue
            nivå, melding = kategori
            treff.append(("fnr", nivå, sti, nr, melding, tekst))


def kontonummer(sti, linjer, valgte, treff):
    """Kontonummer som ikke allerede rapporteres av fnr-sjekken.

    Kontonummer og fnr-k2 bruker samme mod11-vekter, så ethvert gyldig
    kontonummer validerer også som fnr etter 2032-ordningen. Det som skiller
    dem er datoformen i de fire første sifrene, og der vinner fnr-sjekken.

    Utelukkelsen gjelder bare når fnr-sjekken ville sett tallet. Den leser
    11-sifrede tall uten skilletegn, så et formatert kontonummer finner den
    aldri — og med `--sjekk kontonummer` alene kjører den ikke.
    """
    fnr_dekker = "fnr" in valgte
    er_test = spraak.er_testfil(sti)
    for nr, linje in enumerate(linjer, 1):
        for match in siffer.KONTO_MØNSTER.finditer(linje):
            if siffer.del_av_lengre_verdi(linje, match.start(), match.end()):
                continue
            tall = "".join(match.groups())
            if er_test and siffer.er_plassholdersekvens(tall):
                continue
            if not siffer.er_gyldig_konto(tall):
                continue
            if fnr_dekker and match.group(0).isdigit() and (
                    not er_test or siffer.fnr_kategori(tall) is not None):
                # I prod tar fnr-sjekken ethvert uformatert 11-sifret tall; i
                # test kun de som validerer. Formaterte numre ser den aldri.
                continue
            treff.append(("kontonummer", "FUNN", sti, nr,
                          "11 siffer som validerer som kontonummer",
                          match.group(0)))


def kjør_alle(sti, endelse, linjer, valgte, treff):
    """Kjører de valgte sjekkene på én fil."""
    if "nettverk" in valgte:
        nettverk(sti, endelse, linjer, treff)
    if "prosess" in valgte:
        prosess(sti, endelse, linjer, treff)
    if "hemmeligheter" in valgte:
        hemmeligheter(sti, linjer, treff)
    if "jwt" in valgte:
        jwt(sti, linjer, treff)
    if "base64" in valgte:
        base64(sti, linjer, treff)
    if "fnr" in valgte:
        fnr(sti, linjer, treff)
    if "kontonummer" in valgte:
        kontonummer(sti, linjer, valgte, treff)
