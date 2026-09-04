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

# Det eneste domenesuffikset som er godkjent i PRODUKSJONSKODE: Navs egne. Alt
# annet er et funn — også localhost, 127.0.0.1, 0.0.0.0, ::1 og
# host.docker.internal. En lokal adresse i kode som blir med er en
# lokal-profildefault på avveie, ikke noe skriptet skal tie om.
#
# «.local» står bevisst ikke her. Målt i flåten 2026-09-02 finnes elector.local
# (Nais leader elector) og texas.local kun i testkode. Målingen ble gjentatt
# 2026-09-04 over 69 repoer i tre naboteam: ingen av de to navnene finnes i
# prodkode der heller, så suffikset holdes utenfor. Dukker ekte prodbruk opp,
# hører den hjemme som en begrunnet unntaksoppføring, ikke som en oppmyking.
GODKJENTE_PRODSUFFIKSER = (".nav.no", ".adeo.no", ".nais.io")

# Apper adressert med tjenestenavn i klyngen. Dette er Nais' service discovery:
# «http://amt-deltaker» innenfor eget namespace, «http://amt-deltaker.amt» på
# tvers, og den fullt kvalifiserte formen med .svc.cluster.local.
#
# Formen er generell, ikke bundet til ett team. Et repo som skal kunne skannes
# av naboene våre kan ikke ha vårt eget appnavnprefiks som eneste godkjente
# tjenestenavn.
K8S_SUFFIKSER = (".svc.cluster.local", ".svc.nais.local")

# Toppdomener som skiller et ekte domene fra et namespace. «amt-deltaker.amt»
# er service discovery; «evil.io» og «example.com» er verter ute på nettet.
# Lista er bevisst kort og eksplisitt: den skal fange de domenene som faktisk
# dukker opp i kode, ikke være en fullstendig TLD-liste.
TOPPDOMENER = frozenset({
    "no", "se", "dk", "fi", "is", "de", "fr", "nl", "uk", "eu", "us", "ru",
    "com", "org", "net", "int", "biz", "info", "co", "gov", "edu", "mil",
    "io", "dev", "app", "cloud", "ai", "sh", "me", "ms", "tv", "cc", "xyz",
    "tech", "online", "site", "local",
})

# Enkeltledds navn som IKKE er tjenestenavn i klyngen. «localhost» peker på
# poden selv, ikke på en tjeneste, og hører ikke hjemme i kode som deployes.
IKKE_TJENESTENAVN = frozenset({"localhost", "host", "host.docker.internal"})

# Pakkeregistre. En URL hit er et bygg som henter avhengigheter, ikke et kall
# ut fra en kjørende app. Ukjente registre er fortsatt funn — der ligger
# forsyningskjede-signalet.
PAKKEREGISTRE = frozenset({
    "registry.npmjs.org", "npm.pkg.github.com", "maven.pkg.github.com",
    "repo.maven.apache.org", "repo1.maven.org", "plugins.gradle.org",
    "services.gradle.org", "packages.confluent.io",
    "crates.io", "static.crates.io", "pypi.org", "files.pythonhosted.org",
})

# Navnerom, ikke adresser. En xmlns i en SVG eller en $schema i en JSON-fil
# slås aldri opp; strengen er en identifikator.
SKJEMAVERTER = frozenset({
    "www.w3.org", "json-schema.org", "schemas.xmlsoap.org", "xmlns.jcp.org",
})

# Identitetsleverandøren Nav-plattformen faktisk bruker. Kun disse to:
# Altinn, Brønnøysund, Maskinporten og liknende er partnerintegrasjoner som
# varierer per team, og hører hjemme i unntakslista med begrunnelse.
IDENTITETSVERTER = frozenset({
    "login.microsoftonline.com", "graph.microsoft.com",
})

# Lockfiler er maskingenererte, og registeret de peker på er styrt et annet
# sted (.npmrc, pnpm-workspace.yaml, byggfila). Å lese dem gir tusenvis av
# treff på samme vert uten at noen av dem er en beslutning i koden.
LOCKFILER = re.compile(
    r"(^|/)(pnpm-lock\.yaml|yarn\.lock|package-lock\.json|Cargo\.lock"
    r"|[^/]*\.lockfile)$",
)

# Klammet IPv6-vert («http://[::1]:8080») fanges for seg: «]» må med i verten,
# men ikke ellers — der avslutter den en liste eller en Markdown-lenke.
#
# «|», «*» og «(» avslutter også en vert. Målt over 69 nabo-repoer er de tre
# tegnene som faktisk dukker opp midt i et «vertsnavn»: en Markdown-tabell
# («grafana.nav.cloud.nais.io|Grafana») og et regex-literal
# («https://(test|prod).oidc.*difi.*»). «;» og «#» forekom ikke.
URL_MØNSTER = re.compile(
    r"\b(?:https?|wss?)://(\[[0-9A-Fa-f:.]+\](?::\d+)?|[^\s\"'`<>,\)\]\}\\|*(]+)",
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
# En literal som selv er et miljøvariabelnavn er en nøkkel, ikke en verdi:
# «const val AZURE_APP_CLIENT_ID = "AZURE_APP_CLIENT_ID"» sier hvor verdien
# skal hentes fra, den bærer den ikke. Målt hos et naboteam sto 29 av 30
# hemmelighetstreff på denne formen.
MILJØNAVN_LITERAL = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")
# Container-image på formen «registry/sti» eller «registry/sti:tag». Taggen er
# ofte en commit-sha, som ser ut som entropi. Kun små bokstaver, så en
# base64-hemmelighet med store bokstaver eller «+/=» treffer ikke.
IMAGEFORM = re.compile(r"^[a-z0-9][a-z0-9.-]*(?::\d+)?(?:/[a-z0-9._-]+)+$")

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

    # Godkjent i begge scope. Rekkefølgen er poenget: alt som er greit i prod
    # skal også være greit i test, ellers ville testkode blitt strengere
    # vurdert enn koden som faktisk deployes.
    if vert in PAKKEREGISTRE or vert in SKJEMAVERTER or vert in IDENTITETSVERTER:
        return True
    if vert.endswith(K8S_SUFFIKSER):
        return True
    if er_klyngetjeneste(vert):
        return True

    if scope == "prod":
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


def er_klyngetjeneste(vert):
    """Om verten ser ut som en app adressert med Nais' service discovery.

    To former godkjennes: «amt-deltaker» i eget namespace og
    «amt-deltaker.amt» på tvers av namespace. Den kvalifiserte formen skilles
    fra et ekte domene på siste ledd — er det et kjent toppdomene, er strengen
    en vert ute på nettet, ikke et namespace.

    Dette er en heuristikk, og prisen står her: en teststubb som
    «http://test» eller «http://pdl» i produksjonskode slipper nå gjennom, og
    et namespace som deler navn med et toppdomene («app.io») ville blitt lest
    som et domene. Alternativet — å binde formen til ett teams appnavn — gjør
    skriptet ubrukelig for alle andre.
    """
    if _er_ip(vert) or vert in IKKE_TJENESTENAVN:
        return False
    deler = vert.split(".")
    if not all(re.fullmatch(r"[a-z0-9-]+", del_) for del_ in deler):
        return False
    if len(deler) == 1:
        return True
    return len(deler) == 2 and deler[1] not in TOPPDOMENER


def nettverk(sti, endelse, linjer, treff):
    if endelse not in spraak.KODEFILER:
        return
    if LOCKFILER.search(sti):
        # Lockfila er et avtrykk av det byggfila og .npmrc allerede bestemmer.
        # De andre sjekkene leser den fortsatt.
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
                and not NAVNEFORM.match(match.group(2))
                and not MILJØNAVN_LITERAL.match(match.group(2))
                and not IMAGEFORM.match(match.group(2))):
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
