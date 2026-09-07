#!/usr/bin/env python3
"""Finn ellevesifre i hele git-historikken til alle repoene i en teammappe.

Skriver én markdown-fil og én CSV per team, delt på tre akser:

    prod / test          — samme teststi-definisjon som klassifiser.py
    gyldig nummerserie /
    syntetisk eller ugyldig — validate fra wrapperen, samme tabell som kriterier.md
    HEAD / historikk     — om verdien finnes i klonens HEAD nå

Bruk:

    ./script/sveip/fnr-team.py ~/dev/nav/komet
    ./script/sveip/fnr-team.py ~/dev/nav/tiltakspenger --dato 2026-09-04
    ./script/sveip/fnr-team.py ~/dev/nav/valp --ut /tmp/valp.md

Repoer er undermappene som har .git; alt annet i teammappa hoppes over. Wrapperen finnes med
--wrapper eller GITLEAKS_WRAPPER (standard ~/dev/nav/gitleaks-wrapper) og gir både config.toml
med off-id-regelen og validate.py.

Forholdet til klassifiser.py: dette er en lettvektsmatrise for ett team, kjørt rett mot klonene.
klassifiser.py bygger baselinebeviset for flåten vår ut fra et wrapper-sveip, med statuser,
kriteriekoder og PR-oppslag. Teststi, validering og plassholderfilteret er de samme, og importeres
herfra i stedet for å gjentas.

Skriptet sier at nummeret har formen og validerer i en gyldig serie — ikke at det tilhører en
person. Verdier i gyldig serie skrives derfor aldri, verken til stdout eller til filene. Syntetiske
og ugyldige numre er ikke personopplysninger og listes med verdi, som i ikke-reelle-numre.md.

Exit: 0 = ingen treff i gyldig serie i HEAD, 1 = minst ett, 2 = feil i argumenter.
"""
import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HER = Path(__file__).resolve().parent
METAREPO = HER.parent.parent
sys.path.insert(0, str(HER))

# Teststi, plassholderfilter, celle-vasking og kommando-hjelperen er de samme reglene som i
# sveipklassifiseringen. De importeres, slik at en endring i kriteriene slår gjennom begge steder.
from klassifiser import (  # noqa: E402
    SHA, celle, csv_celle, er_teststi, kommando, plassholder_sifre,
)

FALLBACK_GITLEAKS = Path.home() / '.cache/gitleaks-sveip/gitleaks'
# Samme tabell som kriterier.md: kun fnr og dnr er en gyldig nummerserie. Måned 41–52 (hnr,
# Dolly) og 81–92 (tnr, Test-Norge) er syntetiske, og alt som ikke validerer er ugyldig.
GYLDIG_SERIE_TYPER = ('fnr', 'dnr')
GYLDIG = 'gyldig nummerserie'
SYNTETISK = 'syntetisk eller ugyldig'
PARALLELLE_REPOER = 4
MAKS_RADER = 200          # over dette vises én rad per fil; CSV-en har alt
PID_LENKE = 'https://www.skatteetaten.no/deling/folkeregisteret/pid/validering/'
# Filnavn kan selv være et ellevesiffer (mock/person/<nummer>.xml). Da ville stien i en rad for
# gyldig nummerserie båret verdien vi nettopp lot være å skrive. Alle ellevesifre i stier maskeres
# derfor overalt — verdien står uansett i egen kolonne for de radene som skal ha den.
ELLEVE_SIFRE = re.compile(r'(?<!\d)\d{11}(?!\d)')


def masker_sti(sti: str) -> str:
    return ELLEVE_SIFRE.sub('[11 siffer]', sti)


def feil(melding: str):
    print(f'feil: {melding}', file=sys.stderr)
    sys.exit(2)


def finn_gitleaks() -> str:
    binær = shutil.which('gitleaks')
    if binær:
        return binær
    if FALLBACK_GITLEAKS.is_file() and os.access(FALLBACK_GITLEAKS, os.X_OK):
        return str(FALLBACK_GITLEAKS)
    feil(f'fant ikke gitleaks på PATH eller i {FALLBACK_GITLEAKS}')


def finn_validate(wrapper: Path):
    """fnrvalidator-logikken fra wrapperen, hentet på samme måte som i klassifiser.py."""
    if not (wrapper / 'validate.py').exists() or not (wrapper / 'config.toml').exists():
        feil(f'fant ikke config.toml og validate.py i {wrapper} '
             '(bruk --wrapper eller GITLEAKS_WRAPPER)')
    sys.path.append(str(wrapper))   # append: wrapperens filer skal ikke skygge for stdlib
    from validate import validate
    return validate


def repoer_i(mappe: Path) -> list[str]:
    if not mappe.is_dir():
        feil(f'{mappe} er ikke en katalog')
    return sorted(p.name for p in mappe.iterdir() if (p / '.git').exists())


def git(repo: Path, *args, tekst=True):
    return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=tekst)


def skann_repo(gitleaks: str, wrapper: Path, mappe: Path, repo: str) -> list[dict]:
    """Alle refs i klonen, kun off-id-regelen. --exit-code 0 fordi funn er hele poenget."""
    with tempfile.TemporaryDirectory() as tmp:
        rapport = os.path.join(tmp, 'rapport.json')
        r = subprocess.run(
            [gitleaks, 'git', str(mappe / repo),
             '--config', str(wrapper / 'config.toml'),
             '--enable-rule', 'off-id',
             '--log-opts=--all',
             '--report-format', 'json', '--report-path', rapport,
             '--exit-code', '0', '--no-banner'],
            capture_output=True, text=True)
        if r.returncode != 0:
            siste = (r.stderr or r.stdout).strip().splitlines()
            print(f'ADVARSEL: {repo}: gitleaks ga exit {r.returncode}: '
                  f'{siste[-1] if siste else "ingen utskrift"}')
            return []
        if not os.path.isfile(rapport):
            return []
        with open(rapport, encoding='utf-8') as fh:
            return json.load(fh) or []


def head_ellevesifre(mappe: Path, repo: str) -> set[str] | None:
    """Alle 11-sifrede vinduer som finnes i klonens HEAD nå, som én indeks per repo.

    Ett `git grep` per repo i stedet for ett per verdi: team-tiltak ga 19 530 oppslag og minutter
    med venting. Sifferrekker lengre enn elleve gir alle sine 11-vinduer, så et treff midt i en
    lengre rekke telles som før (`git grep -F` matchet delstrenger). `-a` leser binærfiler som
    tekst, som `-F`-oppslaget også traff. None betyr at git feilet — da skal ingen rad påstå noe.
    """
    r = git(mappe / repo, 'grep', '-a', '-h', '-o', '-E', '[0-9]{11,}', 'HEAD', '--')
    if r.returncode not in (0, 1):
        siste = (r.stderr or '').strip().splitlines()
        print(f'ADVARSEL: {repo}: git grep i HEAD ga exit {r.returncode}: '
              f'{siste[-1] if siste else "ingen utskrift"}')
        return None
    vinduer = set()
    for rekke in r.stdout.split():
        for i in range(len(rekke) - 10):
            vinduer.add(rekke[i:i + 11])
    return vinduer


def samle(mappe: Path, repoer: list[str], gitleaks: str, wrapper: Path, validate) -> list[dict]:
    rå = {}
    with ThreadPoolExecutor(max_workers=PARALLELLE_REPOER) as pool:
        for repo, treff in zip(repoer, pool.map(
                lambda r: skann_repo(gitleaks, wrapper, mappe, r), repoer)):
            rå[repo] = treff

    # HEAD-indeksen bygges én gang per repo, parallelt som skanningen.
    with ThreadPoolExecutor(max_workers=PARALLELLE_REPOER) as pool:
        head_indeks = dict(zip(repoer, pool.map(lambda r: head_ellevesifre(mappe, r), repoer)))
    funn = []
    for repo, treff in rå.items():
        if head_indeks[repo] is None:
            print(f'ADVARSEL: {repo}: HEAD-status er ukjent, {len(treff)} treff hoppes over')
            continue
        for v in treff:
            verdi = str(v.get('Secret') or '')
            if not re.fullmatch(r'\d{11}', verdi):
                continue
            if plassholder_sifre(verdi):
                continue        # åtte like, stigende eller synkende sifre er en plassholder
            commit = str(v.get('Commit') or '')
            if not SHA.match(commit):
                print(f'ADVARSEL: {repo}: treff uten gyldig commit-SHA hoppes over')
                continue
            resultat = validate(verdi)
            type_ = resultat.type if resultat.status == 'valid' else 'ugyldig'
            sti = str(v.get('File') or '')
            funn.append({
                'repo': repo,
                'verdi': verdi,
                'type': type_,
                'gyldig_serie': type_ in GYLDIG_SERIE_TYPER,
                'scope': 'test' if er_teststi(sti) else 'prod',
                'i_head': verdi in head_indeks[repo],
                'fil': sti,
                'linje': int(v.get('StartLine') or 0),
                'commit': commit,
                'commitdato': str(v.get('Date') or '')[:10],
            })
    return funn


def kjoringsbevis(mappe: Path, repoer: list[str], gitleaks: str, wrapper: Path,
                  dato: str, antall: int) -> list[str]:
    """Header som gjør fila selvdokumenterende — samme idé som i script/skann og klassifiser.py."""
    nå = datetime.now().astimezone()
    versjon = kommando(gitleaks, 'version') or 'ukjent'
    skript_sha = kommando('git', 'rev-parse', 'HEAD', cwd=METAREPO)
    skript_endret = kommando('git', 'status', '--porcelain', '--',
                             str(HER.relative_to(METAREPO)), cwd=METAREPO)
    wrapper_sha = kommando('git', 'rev-parse', 'HEAD', cwd=wrapper)
    linjer = [
        '```',
        'fnr-team — kjøringsbevis',
        f'  Tidspunkt   : {nå.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")}',
        f'  Dato        : {dato}',
        f'  Teammappe   : {mappe}',
        f'  Repoer      : {len(repoer)} med .git, {antall} treff etter plassholderfilteret',
        f'  gitleaks    : {versjon.removeprefix("v")} ({gitleaks})',
        f'  Regel       : off-id fra {wrapper / "config.toml"}, alle refs (--log-opts=--all)',
        f'  Wrapper     : {wrapper.name} @ {wrapper_sha[:10] or "ukjent"}',
        f'  Skannerkode : script/sveip @ {skript_sha[:10] or "ukjent"}'
        f'{"  (med ukommiterte endringer)" if skript_endret else ""}',
        '',
        '  HEAD-SHA per repo:',
    ]
    for repo in repoer:
        sha = git(mappe / repo, 'rev-parse', 'HEAD').stdout.strip()
        linjer.append(f'    {repo:<40} {sha[:10] or "ukjent"}')
    linjer.append('```')
    return linjer


def matrise(funn) -> list[str]:
    linjer = ['| Kategori | prod | test | Sum |', '|---|---|---|---|']
    for gyldig, i_hode in ((True, True), (True, False), (False, True), (False, False)):
        navn = (GYLDIG if gyldig else SYNTETISK) + ' · ' + ('HEAD' if i_hode else 'historikk')
        celler = []
        sum_f, sum_u = 0, set()
        for scope in ('prod', 'test'):
            treff = [f for f in funn if f['gyldig_serie'] == gyldig and f['i_head'] == i_hode
                     and f['scope'] == scope]
            unike = {(f['repo'], f['verdi']) for f in treff}
            celler.append(f'{len(treff)} / {len(unike)}')
            sum_f += len(treff)
            sum_u |= unike
        linjer.append(f'| {navn} | {celler[0]} | {celler[1]} | {sum_f} / {len(sum_u)} |')
    linjer.append('')
    linjer.append('Hver celle er `forekomster / unike verdier`. En verdi telles unik per repo.')
    return linjer


def seksjon(funn, gyldig: bool, scope: str, i_hode: bool) -> list[str]:
    navn = ((GYLDIG.capitalize() if gyldig else SYNTETISK.capitalize()) + ' — '
            + ('produksjonskode' if scope == 'prod' else 'testkode') + ' — '
            + ('i HEAD' if i_hode else 'kun i historikken'))
    rader = sorted((f for f in funn if f['gyldig_serie'] == gyldig and f['scope'] == scope
                    and f['i_head'] == i_hode),
                   key=lambda f: (f['repo'], f['fil'], f['linje']))
    ut = [f'### {navn}', '']
    if not rader:
        ut += ['ingen', '']
        return ut
    unike = {(f['repo'], f['verdi']) for f in rader}
    ut.append(f'{len(rader)} forekomster, {len(unike)} unike verdier.')
    ut.append('')
    if len(rader) > MAKS_RADER:
        # En generert datafil kan gi tusenvis av rader. Da er tabellen per fil den lesbare
        # formen; hver enkelt forekomst står i CSV-en ved siden av.
        ut.append(f'Mer enn {MAKS_RADER} forekomster — tabellen viser én rad per fil. '
                  'Hver forekomst med commit og linje står i CSV-en.')
        ut.append('')
        ut.append('| Repo | Fil | Forekomster | Unike verdier | Commitdatoer |')
        ut.append('|---|---|---|---|---|')
        per_fil = defaultdict(list)
        for f in rader:
            per_fil[(f['repo'], f['fil'])].append(f)
        for (repo, fil), gruppe in sorted(per_fil.items(),
                                          key=lambda x: (-len(x[1]), x[0])):
            datoer = sorted({f['commitdato'] for f in gruppe if f['commitdato']})
            spenn = datoer[0] if len(datoer) < 2 else f'{datoer[0]}–{datoer[-1]}'
            ut.append(f'| {celle(repo)} | `{masker_sti(celle(fil))}` | {len(gruppe)} '
                      f'| {len({f["verdi"] for f in gruppe})} | {spenn or "ukjent"} |')
        ut.append('')
        return ut
    if gyldig:
        ut.append('| Repo | Fil:linje | Commit | Commitdato | Type |')
        ut.append('|---|---|---|---|---|')
        for f in rader:
            ut.append(f'| {celle(f["repo"])} | `{masker_sti(celle(f["fil"]))}:{f["linje"]}` '
                      f'| `{f["commit"][:7]}` | {f["commitdato"]} | {f["type"]} |')
    else:
        ut.append('| Repo | Fil:linje | Commit | Commitdato | Type | Verdi |')
        ut.append('|---|---|---|---|---|---|')
        for f in rader:
            ut.append(f'| {celle(f["repo"])} | `{masker_sti(celle(f["fil"]))}:{f["linje"]}` '
                      f'| `{f["commit"][:7]}` | {f["commitdato"]} | {f["type"]} '
                      f'| `{f["verdi"]}` |')
    ut.append('')
    return ut


def skriv_md(sti: Path, mappe: Path, repoer, gitleaks, wrapper, dato, funn):
    ut = [f'# Ellevesifre i {mappe.name} — {dato}', '']
    ut += kjoringsbevis(mappe, repoer, gitleaks, wrapper, dato, len(funn))
    ut += ['', '## Matrise', '']
    ut += matrise(funn)
    ut += ['', '## Funn', '',
           'Rekkefølgen er prioritert: gyldig nummerserie først, produksjonskode før testkode, '
           'og det som fortsatt står i HEAD før det som kun ligger i historikken.',
           '',
           'Numre i gyldig serie listes uten verdi — repo, fil, linje og commit peker på dem. '
           'Syntetiske og ugyldige numre kan ikke identifisere en person og listes med verdi, '
           'slik at de kan limes inn i '
           '[Dollys identvalidator](https://dolly.ekstern.dev.nav.no/identvalidator) '
           'som kontroll. Et filnavn kan selv være et ellevesiffer; slike står som '
           '`[11 siffer]` i stiene.', '']
    for gyldig, scope, i_hode in ((True, 'prod', True), (True, 'test', True),
                                  (True, 'prod', False), (True, 'test', False),
                                  (False, 'prod', True), (False, 'test', True),
                                  (False, 'prod', False), (False, 'test', False)):
        ut += seksjon(funn, gyldig, scope, i_hode)
    ut += ['## Om tallene', '',
           'Skriptet sier kun at tallet har formen til et fødselsnummer, validerer mod11 og '
           'ligger i en gyldig nummerserie; det slår ikke opp om nummeret er tildelt noen. '
           f'Oppslag kan gjøres på [Skatteetatens PID-validering]({PID_LENKE}). Et nummer i '
           'gyldig serie er et funn uansett hva oppslaget svarer: er det ikke tildelt i dag, '
           'kan det bli det i morgen.',
           '',
           'HEAD/historikk-aksen er målt mot klonens HEAD på kjøretidspunktet. En klone som ikke '
           'er oppdatert, eller en gren som ikke er hentet ned, flytter grensen mellom de to.',
           '']
    sti.write_text('\n'.join(ut) + '\n', encoding='utf-8')


def skriv_csv(sti: Path, funn):
    with open(sti, 'w', encoding='utf-8', newline='') as fh:
        skriver = csv.writer(fh)
        skriver.writerow(['repo', 'scope', 'gyldig_serie', 'i_head', 'type', 'fil', 'linje',
                          'commit', 'commitdato', 'verdi'])
        for f in sorted(funn, key=lambda f: (not f['gyldig_serie'], f['scope'] != 'prod',
                                             not f['i_head'], f['repo'], f['fil'], f['linje'])):
            skriver.writerow([
                csv_celle(f['repo']), f['scope'], 'ja' if f['gyldig_serie'] else 'nei',
                'ja' if f['i_head'] else 'nei', f['type'], masker_sti(csv_celle(f['fil'])), f['linje'],
                f['commit'][:7], f['commitdato'],
                # Verdien i en gyldig serie skrives aldri, heller ikke her.
                '' if f['gyldig_serie'] else f['verdi'],
            ])


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('teammappe', nargs='?')
    p.add_argument('--dato')
    p.add_argument('--ut')
    p.add_argument('--wrapper',
                   default=os.environ.get('GITLEAKS_WRAPPER',
                                          str(Path.home() / 'dev/nav/gitleaks-wrapper')))
    p.add_argument('-h', '--help', '--hjelp', action='store_true', dest='hjelp')
    try:
        args = p.parse_args()
    except SystemExit:
        raise SystemExit(2)
    if args.hjelp:
        print(__doc__.strip())
        return 0
    if not args.teammappe:
        feil('mangler teammappe. Kjør --hjelp for bruksanvisning.')

    mappe = Path(args.teammappe).expanduser().resolve()
    wrapper = Path(args.wrapper).expanduser()
    dato = args.dato or datetime.now().strftime('%Y-%m-%d')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', dato):
        feil(f'--dato må være YYYY-MM-DD, fikk {dato}')

    repoer = repoer_i(mappe)
    if not repoer:
        feil(f'fant ingen repoer med .git i {mappe}')
    gitleaks = finn_gitleaks()
    validate = finn_validate(wrapper)

    print(f'Skanner {len(repoer)} repoer i {mappe} …')
    funn = samle(mappe, repoer, gitleaks, wrapper, validate)

    md = Path(args.ut).expanduser() if args.ut else mappe / f'fnr-{dato}.md'
    csv_sti = md.with_suffix('.csv')
    md.parent.mkdir(parents=True, exist_ok=True)
    skriv_md(md, mappe, repoer, gitleaks, wrapper, dato, funn)
    skriv_csv(csv_sti, funn)

    gyldige_i_head = [f for f in funn if f['gyldig_serie'] and f['i_head']]
    print(f'{len(funn)} treff. Skrev {md} og {csv_sti.name}.')
    for gyldig in (True, False):
        for i_hode in (True, False):
            treff = [f for f in funn if f['gyldig_serie'] == gyldig and f['i_head'] == i_hode]
            navn = ('gyldig serie' if gyldig else 'syntetisk/ugyldig') + (
                ' · HEAD' if i_hode else ' · historikk')
            unike = {(f['repo'], f['verdi']) for f in treff}
            print(f'  {navn:<28} {len(treff):>6} forekomster, {len(unike):>5} unike')
    return 1 if gyldige_i_head else 0


if __name__ == '__main__':
    sys.exit(main())
