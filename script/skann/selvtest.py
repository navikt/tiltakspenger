#!/usr/bin/env python3
#
# selvtest.py — bygger et fixtur-repo i en midlertidig katalog, kjører
# skann-repo.py mot det, og sjekker at kjerneatferden holder.
#
# Fixturen genereres i stedet for å ligge i git. Plantet innhold som skal
# treffe sjekkene — tokenlignende strenger, gyldige fødselsnummer, eksterne
# adresser — ville trigget GitHubs secret scanning og gjort metarepoets egen
# skann rød om det lå som filer her. Verdiene settes derfor sammen av deler i
# denne fila og skrives ut i tempdir, som slettes etterpå.
#
# Bruk:
#   ./script/skann/selvtest.py [--behold]
#
#   --behold   ikke slett fixturen, og skriv stien. Nyttig når en assert
#              feiler og du vil kjøre skanneren mot fixturen for hånd.
#
# Exit: 0 = alle sjekker passerte, 1 = minst én feilet.
#
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

MAPPE = os.path.dirname(os.path.abspath(__file__))
SKANNER = os.path.join(MAPPE, "skann-repo.py")
sys.path.insert(0, MAPPE)

from skannlib import siffer  # noqa: E402

# --- Byggeklosser -------------------------------------------------------------
#
# Settes sammen i stedet for å stå som literaler, slik at denne fila selv ikke
# ser ut som en hemmelighet eller en ident for skanneren eller for GHAS.
GH_PREFIKS = "gh" + "p_"
TOKENHALE = "ABCdefGHIjklMNOpqrSTUvwx" + "YZ0123456789"
EKSTERN = "https://" + "ekstern-vert" + ".io/api"
EKSTERN_TS = "https://" + "ts-vert" + ".io/api"
JWT = ("ey" + "JhbGciOiJIUzI1NiJ9." + "eyJzdWIiOiJ0ZXN0In0." + "c2lnbmF0dXI")
BASE64 = ("TWFuIGlzIGRpc3Rpbmd1" + "aXNoZWQsIG5vdCBvbmx5"
          + "IGJ5IGhpcyByZWFzb24s" + "IGJ1dCBieQ11")
DOCKER_VERT = "http://" + "host.docker" + ".internal:6969/token"
LOKAL_VERT = "http://" + "local" + "host:8080/health"
K8S_VERT = "http://" + "tiltakspenger" + "-tiltak"
K8S_VERT_NS = "http://" + "tiltakspenger" + "-tiltak.tpts"
FREMMED_NS = "http://" + "annet" + "-app.tpts"


def med_kontrollsifre(ni):
    """Bygger et mod11-gyldig ellevesiffer fra ni sifre, eller None."""
    d = [int(c) for c in ni]
    k1 = siffer.kontrollsiffer(d, siffer.VEKTER_FNR_K1)
    if k1 is None:
        return None
    k2 = siffer.kontrollsiffer(d + [k1], siffer.VEKTER_FNR_K2)
    if k2 is None:
        return None
    return ni + str(k1) + str(k2)


def finn_fnr(dag, måned, krav):
    """Første ellevesiffer med gitt dag og måned som oppfyller `krav`."""
    for n in range(1000):
        kandidat = med_kontrollsifre(f"{dag:02d}{måned:02d}{n:05d}")
        if kandidat and krav(kandidat):
            return kandidat
    raise SystemExit(f"fant ikke testnummer for {dag:02d}.{måned:02d}")


def finn_konto():
    """Kontonummer som validerer mod11, men ikke som fødselsnummer."""
    for n in range(100000):
        kropp = f"90{n:08d}"
        k = siffer.kontrollsiffer([int(c) for c in kropp], siffer.VEKTER_KONTO)
        if k is None:
            continue
        kandidat = kropp + str(k)
        if siffer.er_plassholdersekvens(kandidat):
            continue
        if siffer.er_gyldig_konto(kandidat) and siffer.fnr_kategori(kandidat) is None:
            return kandidat
    raise SystemExit("fant ikke testkontonummer")


def er_ekte(n):
    kat = siffer.fnr_kategori(n)
    return kat is not None and kat[0] == "FUNN"


FNR_EKTE = finn_fnr(1, 1, er_ekte)
FNR_TESTNORGE = finn_fnr(10, 82, lambda n: siffer.fnr_kategori(n) is not None)
FNR_UMULIG_DATO = finn_fnr(31, 2, lambda n: siffer.fnr_ordning(n) is not None)
KONTO = finn_konto()
PLASSHOLDER = "9" * 11


# --- Fixturen -----------------------------------------------------------------

def skriv(rot, sti, innhold):
    full = os.path.join(rot, sti)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(innhold)


def bygg_fixtur(rot):
    """Skriver fixturen og legger alt utenom personvern-filene i git."""
    # --- prodkode: ett treff per sjekk -------------------------------------
    skriv(rot, "src/prod.kt", f"""package fixtur
val ekstern = "{EKSTERN}"
val prosess = ProcessBuilder("ls")
val token = "{GH_PREFIKS}{TOKENHALE}"
val jwt = "{JWT}"
val b64 = "{BASE64}"
val ellevesiffer = "{FNR_EKTE}"
val plassholder = "{PLASSHOLDER}"
val apostrof = "don't" // dokumentasjon: {EKSTERN}
""")
    skriv(rot, "src/konto.kt", f"""package fixtur
val konto = "{KONTO[:4]}.{KONTO[4:6]}.{KONTO[6:]}"
""")
    # --- testkode: samme tall, mildere regel -------------------------------
    skriv(rot, "src/test/test.kt", f"""package fixtur
val ekte = "{FNR_EKTE}"
val testnorge = "{FNR_TESTNORGE}"
val umuligDato = "{FNR_UMULIG_DATO}"
val plassholder = "{PLASSHOLDER}"
""")
    # --- JS: apostrof og backtick avgrenser strenger ------------------------
    skriv(rot, "src/klipp.ts", f"""const x = '//'; fetch('{EKSTERN_TS}');
""")
    # --- compose og env-maler: testkode, aldri deployet -------------------
    skriv(rot, "docker-compose.yml", f"""services:
  app:
    environment:
      URL: "{DOCKER_VERT}"
      IDENT: "{PLASSHOLDER}"
""")
    skriv(rot, ".env-template", f"""URL={DOCKER_VERT}
IDENT={PLASSHOLDER}
""")
    # ... men .env.prod er byggkonfigurasjon som bakes inn i bundelen. Verdien
    # er et ellevesiffer, ikke en URL: fnr-sjekken leser alle filtyper, mens
    # nettverkssjekken kun leser dem som står i KODEFILER.
    skriv(rot, ".env.prod", f"""IDENT={PLASSHOLDER}
""")
    # --- prod: localhost er funn, eget k8s-tjenestenavn er ikke ------------
    skriv(rot, "src/verter.kt", f"""package fixtur
val lokal = "{LOKAL_VERT}"
val tjeneste = "{K8S_VERT}"
val tjenesteNs = "{K8S_VERT_NS}"
val fremmedNs = "{FREMMED_NS}"
""")
    skriv(rot, "src/test/verter.kt", f"""package fixtur
val lokal = "{LOKAL_VERT}"
""")
    # --- rent repo for exit 0 ----------------------------------------------
    skriv(rot, "rent/README.md", "Ingenting å finne her.\n")

    kjør_git(rot, "init", "-q", ".")
    kjør_git(rot, "add", "-A")
    # Commit via plumbing: commit-tree kjører ingen hooks, så fixturen får en
    # ekte HEAD-SHA uten å røre repoets commit-vakter.
    tre = subprocess.run(["git", "-C", rot, "write-tree"], check=True,
                         capture_output=True, text=True).stdout.strip()
    miljø = dict(os.environ, GIT_AUTHOR_NAME="selvtest", GIT_AUTHOR_EMAIL="t@t",
                 GIT_COMMITTER_NAME="selvtest", GIT_COMMITTER_EMAIL="t@t")
    commit = subprocess.run(["git", "-C", rot, "commit-tree", tre, "-m", "fixtur"],
                            check=True, capture_output=True, text=True,
                            env=miljø).stdout.strip()
    kjør_git(rot, "update-ref", "HEAD", commit)

    # --- personvern: skal aldri leses --------------------------------------
    # Usporet i rota, .gitignore-dekket i rota, og i en ignorert undermappe.
    hemmelig = f"""package fixtur
val token = "{GH_PREFIKS}{TOKENHALE}"
val ident = "{FNR_EKTE}"
val url = "{EKSTERN}"
"""
    skriv(rot, "USPORET.kt", hemmelig)
    skriv(rot, "ignorert.kt", hemmelig)
    skriv(rot, "lokalt/skjult.kt", hemmelig)
    skriv(rot, ".gitignore", "ignorert.kt\nlokalt/\n")
    kjør_git(rot, "add", ".gitignore")

    # --- unntakslister ------------------------------------------------------
    skriv(rot, "unntak-tom.txt", "# Tom liste.\n")
    skriv(rot, "unntak-fnr.txt",
          "# Unntak for plassholderen, brukt til å vise scope-delingen.\n"
          f"fnr {PLASSHOLDER}\n")
    skriv(rot, "unntak-ubegrunnet.txt", f"fnr {PLASSHOLDER}\n")


def kjør_git(rot, *args):
    subprocess.run(["git", "-C", rot, *args], check=True,
                   capture_output=True)


def skann(rot, mål=None, *ekstra, unntak_prod=None, unntak_test=None):
    """Kjører skanneren mot `mål` (default fixtur-rota).

    Unntakslistene ligger alltid i fixtur-rota, aldri i det skannede repoet:
    ellers ville et underrepo måtte ha sin egen kopi.
    """
    tom = os.path.join(rot, "unntak-tom.txt")
    kommando = [sys.executable, SKANNER, mål or rot, "--info"]
    kommando += ["--unntak-prod", unntak_prod or tom]
    kommando += ["--unntak-test", unntak_test or tom]
    kommando += list(ekstra)
    return subprocess.run(kommando, capture_output=True, text=True)


def antall_funn(resultat):
    """Plukker tallet ut av «Totalt: N funn i …»."""
    for linje in resultat.stdout.splitlines():
        if linje.startswith("Totalt:"):
            return int(linje.split()[1])
    return None


def funnlinjer(resultat):
    """Bare treff-linjene, uten oppsummering og unntaksstatistikk."""
    linjer = []
    for linje in resultat.stdout.splitlines():
        if linje.startswith("Unntaksstatistikk"):
            break
        if linje.startswith("  ") and ": " in linje and not linje.startswith("  →"):
            linjer.append(linje)
    return linjer


# --- Sjekkene -----------------------------------------------------------------

class Fasit:
    def __init__(self):
        self.ok = 0
        self.feil = []

    def sjekk(self, beskrivelse, betingelse, detalj=""):
        if betingelse:
            self.ok += 1
        else:
            self.feil.append(f"{beskrivelse}{(' — ' + detalj) if detalj else ''}")
        merke = "ok  " if betingelse else "FEIL"
        print(f"  [{merke}] {beskrivelse}")


def kjør_selvtest(rot):
    f = Fasit()
    r = skann(rot)
    ut = r.stdout

    print("\nPersonverngaranti")
    f.sjekk("usporet fil i rota leses ikke", "USPORET.kt" not in ut)
    f.sjekk("gitignorert fil i rota leses ikke", "ignorert.kt" not in ut)
    f.sjekk("gitignorert undermappe leses ikke", "lokalt/skjult.kt" not in ut)
    for navn in ("USPORET.kt", "ignorert.kt", "lokalt/skjult.kt"):
        full = os.path.join(rot, navn)
        f.sjekk(f"{navn} finnes og ville gitt treff",
                os.path.isfile(full) and GH_PREFIKS in open(full, encoding="utf-8").read())

    print("\nKjernetreff, én per sjekk")
    f.sjekk("nettverk", "ikke-godkjent vert" in ut)
    f.sjekk("prosess", "ProcessBuilder" in ut)
    f.sjekk("hemmeligheter", "personal access token" in ut)
    f.sjekk("jwt", "JWT-lignende" in ut)
    f.sjekk("base64", "base64-literal" in ut)
    f.sjekk("fnr", "11 siffer i produksjonskode" in ut)
    f.sjekk("kontonummer", "validerer som kontonummer" in ut)

    print("\nProd- og testskillet")
    f.sjekk("ellevesiffer i prod er funn",
            f"src/prod.kt" in ut and FNR_EKTE in ut)
    f.sjekk("plassholder i prod er funn", PLASSHOLDER in ut)
    linjer_test = [linje for linje in funnlinjer(r) if "src/test/test.kt" in linje]
    f.sjekk("plassholder i test er stille",
            not any(PLASSHOLDER in linje for linje in linjer_test))
    f.sjekk("syntetisk serie i test er INFO",
            any(FNR_TESTNORGE in linje and "INFO" in linje for linje in linjer_test))

    print("\nDatovalidering")
    # Tallet validerer fortsatt mod11 som kontonummer — k2 og kontokontrollen
    # bruker samme vekter — så det rapporteres der. Poenget er at det ikke
    # lenger utgir seg for å være en fødselsdato.
    f.sjekk("31.02 rapporteres ikke som fødselsnummer",
            not any(FNR_UMULIG_DATO in linje and "fødselsnummer" in linje
                    for linje in linjer_test),
            FNR_UMULIG_DATO)
    f.sjekk("31.02 fanges som kontonummer i stedet",
            any(FNR_UMULIG_DATO in linje and "kontonummer" in linje
                for linje in linjer_test))
    f.sjekk("gyldig dato treffer i test",
            any(FNR_EKTE in linje for linje in linjer_test))

    print("\nKommentarklipping")
    f.sjekk("apostrof i Kotlin-streng stopper ikke klippingen",
            not any("prod.kt:9" in linje for linje in funnlinjer(r)))
    f.sjekk("'//' i TS-streng kutter ikke linja",
            "ts-vert.io" in ut)

    print("\nCompose og env-maler er testkode")
    f.sjekk("host.docker.internal i compose er stille",
            not any("docker-compose.yml" in linje for linje in funnlinjer(r)))
    f.sjekk("plassholder i compose er stille",
            not any("docker-compose.yml" in linje and PLASSHOLDER in linje
                    for linje in funnlinjer(r)))
    f.sjekk(".env-template er testkode",
            not any(".env-template" in linje for linje in funnlinjer(r)))
    f.sjekk(".env.prod er fortsatt prod",
            any(".env.prod" in linje for linje in funnlinjer(r)))

    print("\nEnkeltledds verter")
    prod_verter = [linje for linje in funnlinjer(r) if "src/verter.kt" in linje]
    f.sjekk("localhost i prodfil er funn",
            any("localhost" in linje for linje in prod_verter))
    f.sjekk("eget k8s-tjenestenavn i prod er godkjent",
            not any("tiltakspenger-tiltak" in linje and ".tpts" not in linje
                    for linje in prod_verter))
    f.sjekk("namespace-kvalifisert eget navn i prod er godkjent",
            not any("tiltakspenger-tiltak.tpts" in linje for linje in prod_verter))
    f.sjekk("annet namespace i prod er funn",
            any("annet-app.tpts" in linje for linje in prod_verter))
    f.sjekk("localhost i testfil er stille",
            not any("src/test/verter.kt" in linje for linje in funnlinjer(r)))

    print("\nBevis-header")
    header = ut.split("=" * 72)[1] if "=" * 72 in ut else ""
    sha = subprocess.run(["git", "-C", rot, "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    f.sjekk("header finnes", "kjøringsbevis" in header)
    f.sjekk("header bærer full commit-SHA", sha and sha in header, sha[:12])
    f.sjekk("header bærer tidspunkt med sone", "UTC+" in header or "UTC-" in header)
    f.sjekk("header navngir repoet", os.path.basename(rot) in header)

    print("\n--uten-test")
    r_prod = skann(rot, None, "--uten-test")
    prod_linjer = funnlinjer(r_prod)
    f.sjekk("testfunn er borte",
            not any("src/test/" in linje for linje in prod_linjer))
    f.sjekk("prodfunn består",
            any("src/prod.kt" in linje for linje in prod_linjer))
    f.sjekk("testfiler telles som hoppet over",
            "testfiler hoppet over" in r_prod.stdout)

    print("\nHoppet over-blokka")
    f.sjekk("blokka finnes alltid", "Hoppet over" in ut)
    f.sjekk("uten flagg: ingenting hoppet over",
            "ingenting — alle sjekker" in ut or "gitleaks:" in ut)
    f.sjekk("--uten-test står i blokka",
            "test-scope utelatt med --uten-test" in r_prod.stdout)
    r_ug = skann(rot, None, "--uten-gitleaks")
    f.sjekk("--uten-gitleaks står i blokka",
            "slått av med --uten-gitleaks" in r_ug.stdout)
    r_sjekk = skann(rot, None, "--sjekk", "fnr")
    f.sjekk("--sjekk-fravalg står i blokka",
            "nettverk: valgt bort med --sjekk" in r_sjekk.stdout)
    # PATH uten gitleaks, men med git — skanneren trenger git for å lese
    # sporede filer, så en helt tom PATH ville testet noe annet.
    git_mappe = os.path.dirname(shutil.which("git") or "/usr/bin/git")
    tomt = dict(os.environ, PATH=git_mappe)
    r_uten = subprocess.run(
        [sys.executable, SKANNER, rot, "--sjekk", "gitleaks",
         "--unntak-prod", os.path.join(rot, "unntak-tom.txt"),
         "--unntak-test", os.path.join(rot, "unntak-tom.txt")],
        capture_output=True, text=True, env=tomt)
    f.sjekk("manglende verktøy står i blokka",
            "gitleaks ikke på PATH" in r_uten.stdout, r_uten.stdout[-160:])
    f.sjekk("manglende verktøy gir ikke exit-feil", r_uten.returncode in (0, 1),
            f"fikk {r_uten.returncode}")

    print("\nScope-delte unntakslister")
    fasit_uten = antall_funn(r)
    r_test = skann(rot, unntak_test=os.path.join(rot, "unntak-fnr.txt"))
    f.sjekk("testunntak dekker ikke prod-funn",
            antall_funn(r_test) == fasit_uten
            and any(PLASSHOLDER in linje for linje in funnlinjer(r_test)),
            f"{antall_funn(r_test)} mot {fasit_uten}")
    r_prod = skann(rot, unntak_prod=os.path.join(rot, "unntak-fnr.txt"))
    plassholdere = len([linje for linje in funnlinjer(r) if PLASSHOLDER in linje])
    f.sjekk("produnntak dekker prod-funn",
            antall_funn(r_prod) == fasit_uten - plassholdere
            and not any(PLASSHOLDER in linje for linje in funnlinjer(r_prod)),
            f"{antall_funn(r_prod)} mot {fasit_uten} minus {plassholdere}")

    print("\nExit-koder og feilhåndtering")
    f.sjekk("funn gir exit 1", r.returncode == 1, f"fikk {r.returncode}")
    rent = os.path.join(rot, "rent")
    if not os.path.isdir(os.path.join(rent, ".git")):
        kjør_git(rent, "init", "-q", ".")
    kjør_git(rent, "add", "-A")
    r_rent = skann(rot, rent)
    f.sjekk("rent repo gir exit 0", r_rent.returncode == 0,
            f"fikk {r_rent.returncode}: {r_rent.stderr.strip()[:120]}")
    r_arg = skann(rot, None, "--sjekk", "finnesikke")
    f.sjekk("ukjent sjekk gir exit 2", r_arg.returncode == 2, f"fikk {r_arg.returncode}")
    r_beg = skann(rot, unntak_prod=os.path.join(rot, "unntak-ubegrunnet.txt"))
    f.sjekk("unntak uten begrunnelse gir exit 2", r_beg.returncode == 2,
            f"fikk {r_beg.returncode}")
    return f


def hovedprogram():
    argparser = argparse.ArgumentParser(add_help=False)
    argparser.add_argument("--behold", action="store_true")
    argparser.add_argument("-h", "--help", "--hjelp", action="store_true", dest="hjelp")
    args = argparser.parse_args()
    if args.hjelp:
        with open(__file__, encoding="utf-8") as fh:
            fh.readline()
            for linje in fh:
                if not linje.startswith("#"):
                    break
                print(linje[2:].rstrip() if linje.startswith("# ") else linje[1:].rstrip())
        return 0

    rot = tempfile.mkdtemp(prefix="skann-selvtest-")
    try:
        bygg_fixtur(rot)
        fasit = kjør_selvtest(rot)
    finally:
        if args.behold:
            print(f"\nFixturen beholdt: {rot}")
        else:
            shutil.rmtree(rot, ignore_errors=True)

    print()
    if fasit.feil:
        print(f"{len(fasit.feil)} av {fasit.ok + len(fasit.feil)} sjekker feilet:")
        for melding in fasit.feil:
            print(f"  - {melding}")
        return 1
    print(f"Alle {fasit.ok} sjekker passerte.")
    return 0


if __name__ == "__main__":
    sys.exit(hovedprogram())
