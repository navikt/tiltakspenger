#!/usr/bin/env python3
#
# skann-repo.py — skanner et repo for innhold som ikke hører hjemme der:
# nettverksadresser utenfor listen over godkjente verter, prosess- og
# socket-kall, hemmeligheter, base64-blobber, fødselsnummer og kontonummer.
#
# Bakgrunnen er publiseringsjobben i tiltakspenger-libs: hele bygget, tester
# inkludert, kjører i samme jobb som holder packages/contents/id-token/
# attestations: write, og gjør det før artefaktene attesteres. En testfil som
# ringer ut, starter en prosess eller bærer en ekte nøkkel har hele
# publiseringsrettigheten tilgjengelig. Skriptet finner slikt før det står der.
#
# Bruk:
#   ./script/skann/skann-repo.py <repo-sti> [--sjekk a,b,...]
#                                [--unntak-prod <fil>] [--unntak-test <fil>]
#                                [--info]
#
# Argumenter:
#   <repo-sti>     repoet som skal skannes. Leser kun git-sporede filer
#                  (`git ls-files`) og hopper over binærfiler.
#
# Personvern:
#   Skanneren leser kun filer git sporer. Usporede og ignorerte filer åpnes
#   aldri — en utviklers .env, IDE-oppsett og alt annet .gitignore dekker,
#   i rota som i undermapper, blir ikke lest uansett hva de inneholder.
#   --sjekk        kommaseparert liste med sjekker som skal kjøres
#                  (default: alle). Se --hjelp for navnene.
#   --unntak-prod  unntaksliste for produksjonskode
#                  (default: script/skann/skann-unntak-prod.txt)
#   --unntak-test  unntaksliste for testkode
#                  (default: script/skann/skann-unntak-test.txt)
#   --info         tar med INFO-treff (syntetiske testidenter o.l.). INFO-treff
#                  gir aldri exit 1.
#
# Sjekker:
#   nettverk       URL-er med ikke-godkjent vert, i kodefiler
#   prosess        prosess-, socket- og native-kall (jvm, rust, node, python)
#   hemmeligheter  private nøkler, tokens, lange literaler på hemmelighetsnavn
#   jwt            JWT-lignende strenger (egen sjekk: legitime i testfixturer)
#   base64         base64-literaler på 60 tegn eller mer
#   fnr            11-sifrede tall — se prod/test-skillet under
#   kontonummer    11 siffer som validerer som norsk kontonummer
#
# Produksjonskode og testkode:
#   Sjekkene er strengest i prod. Et frittstående 11-sifret tall i
#   produksjonskode er alltid et funn, uavhengig av mod11 og uavhengig av om
#   det er en plassholder — det finnes ingen god grunn til å skrive et der. I
#   testkode valideres tallet mot mod11, og syntetiske serier (Dolly,
#   Test-Norge) rapporteres som INFO.
#
#   Testkode er src/test og src/testFixtures, testkatalog i repo-rota,
#   testmoduler (navn som *-test, *test-common, *-test-core), mock-req-res, og
#   frontendmønstrene *.test.*, *.spec.*, __tests__/, e2e/, playwright/,
#   fixtures/, testdata/ og test-data/, pluss testriggenes konfigurasjon
#   (playwright.config.*, vitest.config.*, jest.config.*). Alt annet er
#   prod, også Nais-manifester, byggconfiger og annen konfig.
#
# Unntakslister:
#   To lister, én per scope, slik at et testunntak aldri kan skjule et funn i
#   produksjonskode. Begge hører til skriptet, ikke til det enkelte repoet: én
#   fil i metarepoet dekker hele flåten.
#
#   Format, én oppføring per linje:
#     sjekk-id regex             gjelder alle repoer
#     repo-navn/sjekk-id regex   gjelder kun det repoet (basename av skannet sti)
#   Hver oppføring MÅ ha en #-begrunnelse på linja over — samme disiplin som
#   zizmor-unntakene. Regexen matches mot matchteksten og mot «sti:matchtekst».
#
#   Hver kjøring avslutter med statistikk per liste over brukte og ubrukte
#   oppføringer, slik at listene kan ryddes før de vokser seg til en sovepute.
#
# Exit:
#   0 = ingen funn, 1 = funn, 2 = feil i argumenter eller unntaksliste.
#
import argparse
import datetime
import os
import subprocess
import sys

MAPPE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MAPPE)

from skannlib import sjekker, spraak, unntak, verktoy  # noqa: E402

EXIT_BRUKSFEIL = 2


def bruksfeil(melding):
    """Skriver en feilmelding til stderr og avslutter med exit 2."""
    print(melding, file=sys.stderr)
    sys.exit(EXIT_BRUKSFEIL)


def sporede_filer(repo):
    """Filene git sporer i repoet, og bare dem.

    Dette er personverngarantien, ikke en implementasjonsdetalj: usporede og
    ignorerte filer åpnes aldri. En utviklers .env, IDE-oppsett, lokale dumper
    og alt annet .gitignore dekker, i rota som i undermapper, leses ikke uansett
    hva de inneholder. Skriv aldri om dette til os.walk eller annen
    filsystemvandring — da faller garantien, og skanneren begynner å lese
    filer som aldri var ment for den.
    """
    resultat = subprocess.run(
        ["git", "-C", repo, "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if resultat.returncode != 0:
        bruksfeil(f"fant ikke git-sporede filer i {repo}: "
                  f"{resultat.stderr.decode('utf-8', 'replace').strip()}")
    return [f for f in resultat.stdout.decode("utf-8", "surrogateescape").split("\0") if f]


def les_tekstfil(full_sti):
    """Returnerer linjene i fila, eller None når fila er binær eller uleselig."""
    try:
        with open(full_sti, "rb") as fh:
            # Sniff først, slik at en stor binærfil ikke leses inn i minnet bare
            # for å bli forkastet.
            start = fh.read(8192)
            if b"\0" in start:
                return None
            rå = start + fh.read()
    except OSError:
        return None
    return rå.decode("utf-8", "replace").splitlines()


def git_verdi(repo, *args):
    """Leser en git-verdi fra repoet, eller None om den ikke finnes."""
    resultat = subprocess.run(["git", "-C", repo, *args],
                              capture_output=True, text=True, check=False)
    if resultat.returncode != 0:
        return None
    return resultat.stdout.strip() or None


def skriv_bevisheader(repo, repo_navn, verktøyversjoner):
    """Skriver hva som ble skannet, når, og med hvilken versjon av hva.

    En lagret utskrift skal kunne stå alene som dokumentasjon: den navngir
    tilstanden ved full commit-SHA, tidspunktet med tidssone, og versjonen av
    hvert verktøy som deltok. Uten dette er en utskrift bare en påstand.
    """
    nå = datetime.datetime.now().astimezone()
    print("=" * 72)
    print("skann-repo — kjøringsbevis")
    print(f"  Tidspunkt   : {nå.strftime('%Y-%m-%d %H:%M:%S %Z (UTC%z)')}")
    print(f"  Repo        : {repo_navn}")
    print(f"  Sti         : {repo}")
    sha = git_verdi(repo, "rev-parse", "HEAD")
    if sha:
        gren = git_verdi(repo, "rev-parse", "--abbrev-ref", "HEAD") or "?"
        print(f"  Commit      : {sha[:7]}  ({sha})")
        print(f"  Gren        : {gren}")
        urent = git_verdi(repo, "status", "--porcelain")
        print(f"  Arbeidstre  : {'endringer utenfor commiten' if urent else 'rent'}")
    else:
        print("  Commit      : (ingen commits i repoet)")
    egen = git_verdi(MAPPE, "rev-parse", "HEAD")
    if egen:
        egen_urent = git_verdi(MAPPE, "status", "--porcelain", "--", MAPPE)
        merke = " + ukommiterte endringer" if egen_urent else ""
        print(f"  Skannerkode : {egen[:7]}  ({egen}){merke}")
    for navn, versjon in sorted(verktøyversjoner.items()):
        print(f"  {navn:<12}: {versjon}")
    print("=" * 72)
    print()


def avkort(tekst, lengde=60):
    tekst = tekst.strip()
    return tekst if len(tekst) <= lengde else tekst[: lengde - 1] + "…"


def skann(repo, valgte, oppføringer, kun_prod=False):
    repo_navn = os.path.basename(repo.rstrip(os.sep))
    treff = []
    undertrykt = {"prod": 0, "test": 0}
    filer = 0
    hoppet_test = 0
    for sti in sporede_filer(repo):
        full = os.path.join(repo, sti)
        if not os.path.isfile(full) or os.path.islink(full):
            continue
        if kun_prod and spraak.er_testfil(sti):
            hoppet_test += 1
            continue
        linjer = les_tekstfil(full)
        if linjer is None:
            continue
        filer += 1
        endelse = os.path.splitext(sti)[1].lower()
        rå = []
        sjekker.kjør_alle(sti, endelse, linjer, valgte, rå)
        scope = spraak.scope(sti)
        for post in rå:
            sjekk, _, _, _, _, tekst = post
            if unntak.dekker(oppføringer, scope, repo_navn, sjekk, sti, tekst):
                undertrykt[scope] += 1
                continue
            treff.append(post)
    return treff, undertrykt, filer, hoppet_test


def skriv_hjelp():
    """Skriver doc-headeren øverst i fila som bruksanvisning."""
    with open(__file__, encoding="utf-8") as fh:
        fh.readline()
        for linje in fh:
            if not linje.startswith("#"):
                break
            print(linje[2:].rstrip() if linje.startswith("# ") else linje[1:].rstrip())


class NorskParser(argparse.ArgumentParser):
    """argparse med norsk feilmelding og exit 2 i stedet for engelsk usage."""

    def error(self, melding):
        bruksfeil(f"ugyldig bruk. Kjør «{self.prog} --hjelp» for bruksanvisning.")


def hovedprogram():
    if {"-h", "--help", "--hjelp"} & set(sys.argv[1:]):
        skriv_hjelp()
        return 0
    if any(a == "--unntak" or a.startswith("--unntak=") for a in sys.argv[1:]):
        bruksfeil("--unntak er delt i --unntak-prod og --unntak-test, slik at "
                  "et testunntak ikke kan dekke et funn i produksjonskode.")

    argparser = NorskParser(prog="skann-repo.py", add_help=False)
    argparser.add_argument("repo", nargs="?")
    argparser.add_argument("--sjekk")
    argparser.add_argument("--unntak-prod", dest="unntak_prod")
    argparser.add_argument("--unntak-test", dest="unntak_test")
    argparser.add_argument("--info", action="store_true")
    argparser.add_argument("--uten-test", action="store_true", dest="uten_test")
    argparser.add_argument("--uten-gitleaks", action="store_true", dest="uten_gitleaks")
    args = argparser.parse_args()

    if args.repo is None:
        bruksfeil("mangler <repo-sti>. Kjør «skann-repo.py --hjelp» for bruksanvisning.")
    repo = os.path.abspath(os.path.expanduser(args.repo))
    if not os.path.isdir(repo):
        bruksfeil(f"{args.repo}: ikke en katalog")

    # Hvert punkt her blir en linje i «Hoppet over»-blokka. Ingenting skal
    # kunne falle ut av en kjøring uten at utskriften sier fra om det.
    hoppet = []

    if args.sjekk:
        valgte = [s.strip() for s in args.sjekk.split(",") if s.strip()]
        ukjente = [s for s in valgte if s not in sjekker.SJEKKER]
        if ukjente:
            bruksfeil(f"ukjent sjekk: {', '.join(ukjente)}. "
                      f"Gyldige: {', '.join(sjekker.SJEKKER)}")
        for navn in sjekker.SJEKKER:
            if navn not in valgte:
                hoppet.append((navn, "valgt bort med --sjekk"))
    else:
        valgte = list(sjekker.SJEKKER)

    if args.uten_test:
        hoppet.append(("testkode", "test-scope utelatt med --uten-test"))

    # Eksterne verktøy: slått av med flagg, eller ikke installert.
    verktøyversjoner = {}
    if "gitleaks" in valgte:
        if args.uten_gitleaks:
            valgte.remove("gitleaks")
            hoppet.append(("gitleaks", "slått av med --uten-gitleaks"))
        else:
            binær = verktoy.finn("gitleaks")
            if binær is None:
                valgte.remove("gitleaks")
                hoppet.append(("gitleaks", "verktøy mangler (gitleaks ikke på PATH)"))
            else:
                verktøyversjoner["gitleaks"] = verktoy.versjon(binær)
    elif args.uten_gitleaks:
        hoppet.append(("gitleaks", "slått av med --uten-gitleaks"))

    valgt_fil = {"prod": args.unntak_prod, "test": args.unntak_test}
    filer = {}
    oppføringer = []
    for scope in ("prod", "test"):
        sti = valgt_fil[scope]
        if sti is None:
            standard = unntak.STANDARDFILER[scope]
            sti = standard if os.path.isfile(standard) else None
        elif not os.path.isfile(sti):
            bruksfeil(f"{sti}: fant ikke unntakslista for {scope}")
        if sti:
            filer[scope] = sti
            oppføringer += unntak.les(scope, sti, sjekker.SJEKKER, bruksfeil)

    repo_navn_tidlig = os.path.basename(repo.rstrip(os.sep))
    skriv_bevisheader(repo, repo_navn_tidlig, verktøyversjoner)

    treff, undertrykt, antall_filer, hoppet_test = skann(
        repo, valgte, oppføringer, kun_prod=args.uten_test)

    if "gitleaks" in valgte:
        gitleaks_treff, feil = verktoy.kjør_gitleaks(repo)
        if feil:
            valgte.remove("gitleaks")
            hoppet.append(("gitleaks", feil))
        else:
            for post in gitleaks_treff:
                sjekk, _, sti, _, _, tekst = post
                if args.uten_test and spraak.er_testfil(sti):
                    continue
                scope = spraak.scope(sti)
                if unntak.dekker(oppføringer, scope, repo_navn_tidlig, sjekk, sti, tekst):
                    undertrykt[scope] += 1
                    continue
                treff.append(post)

    synlige = [t for t in treff if t[1] == "FUNN" or args.info]
    funn = [t for t in treff if t[1] == "FUNN"]
    skjulte_info = len(treff) - len(funn)
    repo_navn = os.path.basename(repo.rstrip(os.sep))

    linje = f"Skannet {antall_filer} sporede tekstfiler"
    if hoppet_test:
        linje += f" ({hoppet_test} testfiler hoppet over)"
    print(linje)
    if filer:
        for scope in ("prod", "test"):
            if scope in filer:
                print(f"Unntaksliste ({scope}): {filer[scope]}")
    else:
        print("Unntakslister: ingen")
    print()

    for sjekk in sjekker.SJEKKER:
        if sjekk not in valgte:
            continue
        egne = [t for t in synlige if t[0] == sjekk]
        antall_funn = len([t for t in funn if t[0] == sjekk])
        antall_info = len([t for t in treff if t[0] == sjekk and t[1] == "INFO"])
        if egne:
            print(f"[{sjekk}]")
            for _, nivå, sti, nr, melding, tekst in sorted(egne, key=lambda t: (t[2], t[3])):
                merke = "" if nivå == "FUNN" else "INFO: "
                print(f"  {sti}:{nr}: {merke}{melding} ({avkort(tekst)})")
        deler = [f"{antall_funn} funn"]
        if antall_info:
            deler.append(f"{antall_info} INFO")
        print(f"  → {sjekk}: {', '.join(deler)}")
        print()

    if skjulte_info and not args.info:
        print(f"{skjulte_info} INFO-treff er skjult. Kjør med --info for å se dem.")
    antall = len(set(t[2] for t in funn))
    print(f"Totalt: {len(funn)} funn i {antall} {'fil' if antall == 1 else 'filer'}.")

    unntak.skriv_statistikk(oppføringer, filer, repo_navn, valgte, undertrykt, print)

    # Alltid, også når ingenting ble hoppet over: en tom blokk er også et svar.
    print()
    print("Hoppet over")
    if hoppet:
        for navn, grunn in hoppet:
            print(f"  {navn}: {grunn}")
    else:
        print("  ingenting — alle sjekker kjørte, både prod og test")
    return 1 if funn else 0


if __name__ == "__main__":
    sys.exit(hovedprogram())
