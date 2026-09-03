#!/usr/bin/env python3
"""Klassifiser treffene fra et gitleaks-wrapper-sveip etter kriterier.md, og bygg baselinebeviset.

Leser rapportene navikt/gitleaks-wrapper har skrevet (reports/<repo>.json), gir hvert treff status
etter reglene i kriterier.md, skriver review.json i wrapperens format (så run.py report/show viser
statusene) og bearbeider resultatet videre i metarepoets gitignorerte reports/sveip-<dato>/ (filene er
beskrevet i README.md).

Bruk (fra metarepoets rot):

    ./script/sveip/klassifiser.py                 # tørrkjøring: fordeling og avvik, skriver ingenting
    ./script/sveip/klassifiser.py --write         # skriv review.json i wrapperen og reports/sveip-<dato>/
    ./script/sveip/klassifiser.py --write --regler-vinner   # nullstill manuelle avgjørelser i review.json

Wrapperen finnes med --wrapper eller GITLEAKS_WRAPPER (standard ~/dev/nav/gitleaks-wrapper). Sveipdatoen
leses fra rapportfilenes tidsstempel, eller gis med --dato.

Skriver aldri en treffverdi i ekte serie, en Nav-ident, en e-post eller et passord til stdout eller fil.
Endrer ingenting i wrapperens repos/ (kun lesende git-kommandoer) og kjører ikke sveipet på nytt.
"""
import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

HER = Path(__file__).resolve().parent
METAREPO = HER.parent.parent
KRITERIER = HER / 'kriterier.md'

OK, VIOLATION, UNSURE = 'ok', 'violation', 'unsure'
STRENGHET = {OK: 0, UNSURE: 1, VIOLATION: 2}

TESTSTI = re.compile(
    r'(^|/)(test|tests|testdata|__tests__|fixtures?|mocks?|mockdata|data|e2e|cypress|playwright|stories|storybook'
    r'|demo|local|lokal|local-migrations?|mock-req-res|labs)(/|$)'
    r'|\.(test|spec|stories)\.[a-z]+$'
    r'|Test[A-Za-z]*\.(kt|java|ts|tsx|js|py)$'
    r'|(^|/)src/test/'
    r'|[Mm]ock|[Ff]ake'
)
LOKALE_VERTER = {'localhost', 'host.docker.internal', '127.0.0.1'}
DEV_PASSORD = {'postgres', 'test', 'password', 'passord', 'passord1', 'hemmelig', 'hemmelighet', 'testpassord',
               'dummy', 'secret', 'admin', 'root', ''}
DB_URL = re.compile(r'://(?:([^:@/]*)(?::([^@/]*))?@)?([^:/?]+)')
PASSORD_PARAM = re.compile(r'[?&]password=([^&"\'\s]*)')
PLASSHOLDER = re.compile(r'<[a-zæøå_-]+>|\$\{?[a-zA-Z_]')   # <vert>, ${vert}, $vert
IKKE_REELLE_TYPER = ('ugyldig', 'tnr', 'dnr-and-tnr', 'hnr', 'dnr-and-hnr')
SHA = re.compile(r'^[0-9a-f]{7,40}$')            # commit-SHA-er fra rapportene brukes som git- og API-argumenter
KONTROLLTEGN = re.compile(r'[\x00-\x1f\x7f]')


def gyldig_treff(v: dict, repo: str) -> bool:
    """Rapportfeltene kommer fra repo-innhold (filnavn, verdier). Alt som brukes som argument til git/gh
    må ha ventet form; ellers hoppes treffet over med beskjed, så et rart filnavn eller et redigert
    rapportfelt aldri blir et flagg til et verktøy."""
    if not SHA.match(str(v.get('Commit', ''))):
        print(f'ADVARSEL: {repo}: treff uten gyldig commit-SHA hoppes over ({v.get("Fingerprint", "?")[:60]})')
        return False
    try:
        int(v.get('StartLine') or 0)
    except (TypeError, ValueError):
        print(f'ADVARSEL: {repo}: treff med ugyldig linjenummer hoppes over ({v.get("Fingerprint", "?")[:60]})')
        return False
    return True


def celle(tekst: str) -> str:
    """Tekst fra rapportene (filnavn o.l.) inn i en markdown-tabellcelle: ingen kontrolltegn, ingen
    rørtegn eller backticks som bryter cella."""
    return KONTROLLTEGN.sub('', str(tekst)).replace('|', '\\|').replace('`', "'")


def csv_celle(tekst) -> str:
    """Verner mot formelinjeksjon når CSV-en åpnes i et regneark: celler som begynner med = + - @ får en apostrof foran."""
    tekst = KONTROLLTEGN.sub('', str(tekst))
    return "'" + tekst if tekst[:1] in ('=', '+', '-', '@') else tekst


class Sveip:
    """Stier og hjelpere for ett wrapper-sveip."""

    def __init__(self, wrapper: Path, dato: str | None):
        self.wrapper = wrapper
        self.rapporter = wrapper / 'reports'
        self.repos = wrapper / 'repos'
        self.review = wrapper / 'review.json'
        if not (self.rapporter.is_dir() and (wrapper / 'run.py').exists() and (wrapper / 'validate.py').exists()):
            sys.exit(f'Fant ikke gitleaks-wrapper med reports/ i {wrapper} (bruk --wrapper eller GITLEAKS_WRAPPER)')
        sys.path.append(str(wrapper))   # append: wrapperens filer skal ikke skygge for stdlib
        from validate import validate  # fnrvalidator-logikken i wrapperen
        self.validate = validate
        gitleaks_filer = sorted((self.rapporter / 'gitleaks').glob('*.json'))
        if not gitleaks_filer:
            sys.exit(f'Ingen gitleaks-rapporter i {self.rapporter / "gitleaks"}')
        tidspunkt = [datetime.fromtimestamp(f.stat().st_mtime) for f in gitleaks_filer]
        self.sveip_fra, self.sveip_til = min(tidspunkt), max(tidspunkt)
        self.dato = dato or self.sveip_til.strftime('%Y-%m-%d')
        self.ut = METAREPO / 'reports' / f'sveip-{self.dato}'

    def rapportfiler(self):
        return sorted(p for p in self.rapporter.glob('*.json') if p.name != 'summary.json')

    def repoer(self):
        """Alle klonene i repos/ — også de uten treff."""
        return sorted(p.name for p in self.repos.iterdir() if (p / '.git').exists())

    def git(self, repo: str, *args) -> str:
        return subprocess.run(['git', *args], cwd=self.repos / repo, capture_output=True, text=True).stdout

    def fillinjer(self, repo: str, commit: str, sti: str) -> list[str]:
        r = subprocess.run(['git', 'show', f'{commit}:{sti}'], cwd=self.repos / repo, capture_output=True)
        if r.returncode != 0:
            return []
        try:
            return r.stdout.decode('utf-8').splitlines()
        except UnicodeDecodeError:
            return r.stdout.decode('latin-1').splitlines()

    def kildelinjer(self, repo: str, commit: str, sti: str, linje: int, verdi: str = '') -> list[str]:
        """Kandidatlinjer for et treff (til mønstersjekk — skrives aldri ut): linja rapporten peker på,
        pluss alle linjer i fila som inneholder verdien. trufflehog oppgir av og til linjenummer i
        diffen i stedet for i fila, derfor begge."""
        linjer = self.fillinjer(repo, commit, sti)
        kandidater = [linjer[linje - 1]] if 0 < linje <= len(linjer) else []
        if verdi:
            kandidater += [l for l in linjer if verdi in l and l not in kandidater]
        return kandidater

    def commitdato(self, treff) -> str:
        d = str(treff.get('Date', ''))
        if re.match(r'\d{4}-\d{2}-\d{2}', d):
            return d[:10]
        return self.git(treff['RepositoryName'], 'show', '-s', '--format=%cs', treff['Commit']).strip()

    def offid_type(self, verdi: str) -> str:
        r = self.validate(verdi)
        return r.type if r.status == 'valid' else 'ugyldig'


def er_teststi(sti: str) -> bool:
    return bool(TESTSTI.search(sti))


def plassholder_sifre(sifre: str) -> bool:
    return len(set(sifre)) == 1 or sifre in '0123456789' or sifre in '9876543210'


def les_treff(s: Sveip):
    treff = []
    for fil in s.rapportfiler():
        for v in json.load(open(fil, encoding='utf-8')):
            v['RepositoryName'] = fil.stem
            if gyldig_treff(v, fil.stem):
                treff.append(v)
    return treff


def commitmelding_treff(s: Sveip) -> Counter:
    """trufflehog-treff uten filreferanse (commit-meldinger) — utenfor wrapperens review-modell."""
    c = Counter()
    for fil in sorted((s.rapporter / 'trufflehog').glob('*.json')):
        for linje in open(fil, encoding='utf-8'):
            if not linje.lstrip().startswith('{'):
                continue
            d = json.loads(linje)
            if 'file' not in d['SourceMetadata']['Data']['Git']:
                c[(fil.stem, d['DetectorName'])] += 1
    return c


def klassifiser(s: Sveip, treff, hnr_i_testdata):
    """Returnerer (status, kriterium) for ett treff etter kriterier.md."""
    regel = treff['RuleID']
    repo = treff['RepositoryName']
    sti = treff['File']
    verdi = str(treff['Secret'])
    linje = int(treff['StartLine'] or 0)

    if regel == 'off-id':
        t = s.offid_type(verdi)
        if t == 'ugyldig':
            return OK, 'offid-ugyldig'
        if t in ('tnr', 'dnr-and-tnr'):
            return OK, 'offid-tnr'
        if t in ('hnr', 'dnr-and-hnr'):
            if er_teststi(sti):
                return OK, 'offid-hnr-teststi'
            if verdi in hnr_i_testdata[repo]:
                return OK, 'offid-hnr-samme-som-testdata'
            return OK, 'offid-hnr-utenfor-teststi'
        if t in ('fnr', 'dnr'):
            return VIOLATION, 'offid-fnr-ekte-serie'
        raise AssertionError(f'ukjent validate-type {t}')

    if regel == 'nav-ident':
        if verdi[0].upper() == 'Z':
            return OK, 'navident-z-testbruker'
        if plassholder_sifre(verdi[1:]):
            return OK, 'navident-plassholder'
        return VIOLATION, 'navident-mulig-ansatt'

    if regel in ('nav-email', 'trygdeetaten-email', 'slack-email'):
        return OK, 'epost-jobbadresse'

    if regel in ('JDBC', 'Postgres'):
        kandidater = s.kildelinjer(repo, treff['Commit'], sti, linje)
        kl = kandidater[0] if kandidater else ''
        if sti.endswith('build.gradle.kts') and 'com.oracle.database' in kl:
            return OK, 'db-maven-koordinat'
        m = DB_URL.search(verdi)
        bruker, passord_uri, vert = m.groups() if m else ('', '', '')
        pm = PASSORD_PARAM.search(verdi)
        passord = pm.group(1) if pm else (passord_uri or '')
        if re.search(r'://<[a-zæøå_-]+>', kl) or PLASSHOLDER.search(vert) or PLASSHOLDER.search(passord):
            return OK, 'db-plassholder-mal'
        if not m:
            return UNSURE, 'db-ukjent'
        if vert in LOKALE_VERTER and passord in DEV_PASSORD:
            return OK, 'db-lokal-utviklingsdatabase'
        if '.' not in vert and re.search(r'(^|/)(lokal|local)', sti) and passord in DEV_PASSORD:
            return OK, 'db-compose-tjenestenavn'
        return UNSURE, 'db-ukjent'

    if regel == 'generic-api-key':
        kandidater = s.kildelinjer(repo, treff['Commit'], sti, linje, verdi)
        if any(re.search(rf'\b{re.escape(verdi)}\s*=', kl) for kl in kandidater):
            return OK, 'gak-parameternavn'
        if re.search(r'\.nais/vars/[^/]+\.ya?ml$', sti) and re.fullmatch(r'[a-z0-9.-]+', verdi):
            return OK, 'gak-vertsnavn-nais-vars'
        if re.search(r'(^|/)local-migrations?/', sti) and any(
                kl.lstrip().upper().startswith(('INSERT', 'VALUES', '(')) for kl in kandidater):
            return OK, 'gak-seed-verdi'
        return UNSURE, 'gak-ukjent'

    if regel == 'TrelloApiKey':
        if any('trello.com/c/' in kl for kl in s.kildelinjer(repo, treff['Commit'], sti, linje, verdi)):
            return OK, 'trello-kortlenke'
        return UNSURE, 'trello-ukjent'

    return UNSURE, f'ukjent-regel-{regel}'


def nokkel(t) -> str:
    return f"{t['RepositoryName']}:{t['Fingerprint']}"


def kjor(s: Sveip, regler_vinner: bool):
    """Klassifiserer alle treff. Returnerer (beslutninger, per_nokkel, manuelle, eksisterende)."""
    alle = les_treff(s)
    hnr_i_testdata = defaultdict(set)
    for t in alle:
        if t['RuleID'] == 'off-id' and er_teststi(t['File']) and s.offid_type(str(t['Secret'])) in ('hnr', 'dnr-and-hnr'):
            hnr_i_testdata[t['RepositoryName']].add(str(t['Secret']))

    beslutninger = []                  # (treff, status, kriterium)
    per_nokkel = {}                    # review-nøkkel -> strengeste regelstatus
    for t in alle:
        status, kriterium = klassifiser(s, t, hnr_i_testdata)
        beslutninger.append((t, status, kriterium))
        n = nokkel(t)
        if n not in per_nokkel or STRENGHET[status] > STRENGHET[per_nokkel[n]]:
            per_nokkel[n] = status

    eksisterende = {}
    if s.review.exists():
        try:
            eksisterende = json.load(open(s.review, encoding='utf-8'))
        except json.JSONDecodeError:
            sys.exit(f'{s.review} er ikke gyldig JSON — rett eller flytt den før kjøring')
    manuelle = {}                      # nøkkel -> (manuell status, regelstatus)
    if not regler_vinner:
        for n, regel_status in per_nokkel.items():
            lagret = eksisterende.get(n)
            if lagret in (OK, VIOLATION) and lagret != regel_status:
                manuelle[n] = (lagret, regel_status)
                per_nokkel[n] = lagret
    return beslutninger, per_nokkel, manuelle, eksisterende


def skriv_oversikt(beslutninger, per_nokkel, manuelle):
    per_repo = defaultdict(Counter)
    per_krit = Counter()
    for t, status, krit in beslutninger:
        per_repo[t['RepositoryName']][per_nokkel[nokkel(t)]] += 1
        per_krit[(t['RuleID'], krit, status)] += 1
    print(f'{len(beslutninger)} treff, {len(per_nokkel)} review-nøkler\n')
    print(f"{'repo':42s} {'treff':>6s} {'ok':>6s} {'viol.':>6s} {'unsure':>6s}")
    tot = Counter()
    for repo in sorted(per_repo):
        c = per_repo[repo]
        tot.update(c)
        print(f'{repo:42s} {sum(c.values()):6d} {c[OK]:6d} {c[VIOLATION]:6d} {c[UNSURE]:6d}')
    print(f"{'SUM':42s} {sum(tot.values()):6d} {tot[OK]:6d} {tot[VIOLATION]:6d} {tot[UNSURE]:6d}\n")
    print('Regelutfall (regel, kriterium, status): antall')
    for (regel, krit, status), n in sorted(per_krit.items()):
        print(f'  {regel:20s} {krit:32s} {status:9s} {n:5d}')
    sett = defaultdict(set)
    for t, status, _ in beslutninger:
        sett[nokkel(t)].add(status)
    konflikter = sum(1 for v in sett.values() if len(v) > 1)
    print(f'\nNøkler med flere treff på samme linje og ulik status: {konflikter}')
    print(f'Manuelle avgjørelser i review.json som avviker fra reglene: {len(manuelle)}')
    for n, (man, regel) in sorted(manuelle.items()):
        print(f'  {n}: manuelt {man}, regel {regel}')


# --- oppfølging og bevis ----------------------------------------------------

def oppfolging(s: Sveip, repo: str, verdi: str, funn_commits: set[str]) -> dict:
    """Status for en violation-verdi i klonens HEAD, uten å avsløre verdien.
    Returnerer {'i_head': bool, 'tekst': str} — teksten sier hvor mange filer, eller hvilken commit som fjernet den."""
    if not verdi:
        return {'i_head': False, 'tekst': 'tom verdi — ikke slått opp'}
    head = s.git(repo, 'grep', '-c', '-F', '-e', verdi, 'HEAD', '--').splitlines()
    if head:
        return {'i_head': True, 'tekst': f'{len(head)} fil{"er" if len(head) != 1 else ""} i HEAD'}
    logg = s.git(repo, 'log', '--first-parent', '--format=%h%x09%cs', f'-S{verdi}', 'HEAD').splitlines()
    if logg:
        sha, dato = logg[0].split('\t')
        return {'i_head': False, 'tekst': f'fjernet fra main i {sha} ({dato})'}
    på_main = set(s.git(repo, 'rev-list', 'HEAD').split())
    if not (funn_commits & på_main):
        return {'i_head': False, 'tekst': 'kun på gren utenfor main, aldri på main'}
    logg = s.git(repo, 'log', '--format=%h%x09%cs', f'-S{verdi}', 'HEAD').splitlines()
    if logg:
        sha, dato = logg[0].split('\t')
        return {'i_head': False, 'tekst': f'fjernet i {sha} ({dato}) på PR-grenen som la den til — aldri i et main-snapshot'}
    return {'i_head': False, 'tekst': 'ikke i HEAD (fjernet på annen måte — sjekk manuelt)'}


def pr_oppslag(s: Sveip, repo: str, sha: str) -> str:
    """Pull requests GitHub knytter til commiten (`commits/<sha>/pulls`), mellomlagret i sveipmappa så
    beviset ikke endrer seg mellom kjøringer. Tom streng = direkte push uten PR."""
    cache_fil = s.ut / 'pr-oppslag.json'
    cache = json.load(open(cache_fil, encoding='utf-8')) if cache_fil.exists() else {}
    n = f'{repo}:{sha}'
    if not (SHA.match(sha) and re.fullmatch(r'[A-Za-z0-9._-]+', repo)):
        return 'ikke slått opp (ugyldig repo/sha)'
    if n not in cache:
        r = subprocess.run(['gh', 'api', f'repos/navikt/{repo}/commits/{sha}/pulls',
                            '--jq', '[.[] | "#\\(.number) (" + (if .merged_at then "merget " + .merged_at[:10] elif .state == "open" then "åpen" else "lukket uten merge" end) + ")"] | join(", ")'],
                           capture_output=True, text=True)
        cache[n] = r.stdout.strip() if r.returncode == 0 else None
        cache['_oppslag'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        s.ut.mkdir(parents=True, exist_ok=True)
        json.dump(cache, open(cache_fil, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    v = cache[n]
    return 'ikke slått opp (gh feilet)' if v is None else v


def kommando(*args, cwd=None) -> str:
    try:
        r = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, timeout=120)
        return r.stdout.strip() if r.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def kjoringsbevis(s: Sveip, antall_treff: int) -> list[str]:
    """Header som gjør baselinebeviset selvdokumenterende — samme idé som script/skann."""
    nå = datetime.now().astimezone()
    skript_sha = kommando('git', 'rev-parse', 'HEAD', cwd=METAREPO)
    skript_endret = kommando('git', 'status', '--porcelain', '--', str(HER.relative_to(METAREPO)), cwd=METAREPO)
    wrapper_sha = kommando('git', 'rev-parse', 'HEAD', cwd=s.wrapper)
    wrapper_gren = kommando('git', 'branch', '--show-current', cwd=s.wrapper)
    gitleaks = kommando('docker', 'run', '--rm', '--network', 'none', 'zricethezav/gitleaks:latest', 'version') or 'ikke målt (docker utilgjengelig)'
    gitleaks_digest = kommando('docker', 'image', 'inspect', 'zricethezav/gitleaks:latest', '--format', '{{index .RepoDigests 0}}')
    trufflehog = kommando('docker', 'run', '--rm', '--network', 'none', 'trufflesecurity/trufflehog:latest', '--version') or 'ikke målt (docker utilgjengelig)'
    trufflehog_digest = kommando('docker', 'image', 'inspect', 'trufflesecurity/trufflehog:latest', '--format', '{{index .RepoDigests 0}}')
    repoer = s.repoer()
    return [
        '```',
        'klassifiser-sveip — kjøringsbevis',
        f'  Tidspunkt      : {nå.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)")}',
        f'  Sveip          : rapportfiler skrevet {s.sveip_fra.strftime("%Y-%m-%d %H:%M")}–{s.sveip_til.strftime("%H:%M")} (wrapperens reports/)',
        f'  Repoer         : {len(repoer)} kloner i repos/, {len(s.rapportfiler())} med treff, {antall_treff} treff',
        f'  Wrapper        : navikt/gitleaks-wrapper @ {wrapper_sha[:10]} ({wrapper_gren or "løsrevet HEAD"}), klone {s.wrapper.name}/',
        f'  Skannerkode    : script/sveip @ {skript_sha[:10]}{"  (med ucommittede endringer)" if skript_endret else ""}',
        f'  gitleaks       : {gitleaks.removeprefix("v")}  {gitleaks_digest}',
        f'  trufflehog     : {trufflehog.removeprefix("trufflehog ")}  {trufflehog_digest}',
        f'  Kriterier      : script/sveip/kriterier.md (kopi i denne mappa)',
        '```',
    ]


def skriv_alt(s: Sveip, beslutninger, per_nokkel, manuelle, eksisterende):
    s.ut.mkdir(parents=True, exist_ok=True)

    # 1. review.json til wrapperen (backup av det som lå der først, hvis innholdet endres)
    nytt = dict(sorted(per_nokkel.items()))
    if eksisterende and eksisterende != nytt:
        bak = s.ut / f'review_bak-{datetime.now().strftime("%Y-%m-%dT%H%M%S")}.json'
        shutil.copy2(s.review, bak)
        print(f'Backup av wrapperens review.json: {bak}')
    with open(s.review, 'w', encoding='utf-8') as f:
        json.dump(nytt, f, indent=2, ensure_ascii=False)
    shutil.copy2(s.review, s.ut / 'review.json')
    print(f'Skrev {s.review} ({len(per_nokkel)} nøkler)')

    # 2. begrunnelser
    with open(s.ut / 'begrunnelser.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['repo', 'status', 'regelstatus', 'kriterium', 'regel', 'verktoy', 'scope', 'fil', 'commit', 'linje', 'commitdato'])
        for t, status, krit in beslutninger:
            w.writerow([csv_celle(x) for x in (t['RepositoryName'], per_nokkel[nokkel(t)], status, krit, t['RuleID'], t.get('Tool', ''),
                        'test' if er_teststi(t['File']) else 'prod', t['File'], t['Commit'][:10], t['StartLine'], s.commitdato(t))])

    # 3. ikke-reelle numre (aldri ekte serie)
    skriv_ikke_reelle(s, beslutninger)

    # 4. kriteriekopi
    shutil.copy2(KRITERIER, s.ut / 'kriterier.md')

    # 5. baselinebevis
    skriv_bevis(s, beslutninger, per_nokkel, manuelle)

    # 6. wrapperens egen rapport
    r = subprocess.run([sys.executable, 'run.py', 'report'], cwd=s.wrapper, capture_output=True, text=True)
    (s.ut / 'rapport.txt').write_text(r.stdout + r.stderr, encoding='utf-8')
    print(f'Skrev {s.ut}/{{baselinebevis.md, begrunnelser.csv, ikke-reelle-numre.md, rapport.txt, kriterier.md}}')
    todo = re.search(r'Todo: (\d+)', r.stdout)
    if not todo or todo.group(1) != '0':
        print('ADVARSEL: run.py report viser ikke Todo: 0 — sjekk rapport.txt')


def ikke_reelle(s: Sveip, beslutninger):
    """Unike ikke-reelle 11-sifre (aldri ekte serie): per repo og type, og samlet per type."""
    per_repo = defaultdict(lambda: defaultdict(set))
    per_type = defaultdict(set)
    for t, _, _ in beslutninger:
        if t['RuleID'] != 'off-id':
            continue
        verdi = str(t['Secret'])
        typ = s.offid_type(verdi)
        if typ in IKKE_REELLE_TYPER:
            per_repo[t['RepositoryName']][typ].add(verdi)
            per_type[typ].add(verdi)
    return per_repo, per_type


def dolly_kontroll(s: Sveip, per_type: dict[str, set[str]]) -> str:
    """Sammenholder Dollys nedlasting (identvalidering.csv i sveipmappa) med lista over ikke-reelle numre.
    Reelle numre kjennes på erSyntetisk = false; erIProd er tom for syntetiske og ugyldige numre."""
    fil = s.ut / 'identvalidering.csv'
    alle = set().union(*per_type.values()) if per_type else set()
    if not fil.exists():
        return ('Ikke dokumentert i denne mappa ennå: lim lista inn i Dollys identvalidator, last ned `identvalidering.csv` '
                'derfra, legg den i denne mappa og kjør skriptet på nytt.')
    with open(fil, encoding='utf-8-sig', newline='') as f:
        rader = list(csv.DictReader(f, delimiter=';'))
    if not rader or 'ident' not in rader[0] or 'erSyntetisk' not in rader[0]:
        return f'`{fil.name}` ligger her, men har ikke Dollys kolonner (forventet `ident;…;erSyntetisk;erGyldig;erIProd;…`).'

    def verdi(r, k):
        return str(r.get(k) or '').strip().lower()

    identer = {r['ident'].strip() for r in rader}
    syntetiske = [r for r in rader if verdi(r, 'erSyntetisk') == 'true']
    testnorge = sum(1 for r in syntetiske if verdi(r, 'erTestnorgeIdent') == 'true')
    ugyldige = sum(1 for r in rader if verdi(r, 'erGyldig') == 'false')
    reelle = [r for r in rader if verdi(r, 'erSyntetisk') == 'false']
    i_prod = [r for r in rader if verdi(r, 'erIProd') == 'true']
    mangler = alle - identer
    ekstra = identer - alle
    tid = datetime.fromtimestamp(fil.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
    egne = (len(per_type.get('tnr', set()) | per_type.get('dnr-and-tnr', set())),
            len(per_type.get('hnr', set()) | per_type.get('dnr-and-hnr', set())),
            len(per_type.get('ugyldig', set())))
    deler = [f'`{fil.name}` (lastet ned fra Dolly, filtid {tid}): {len(rader)} numre kontrollert — '
             f'{len(syntetiske)} syntetiske ({testnorge} Test-Norge, {len(syntetiske) - testnorge} Dolly-serien), '
             f'{ugyldige} ugyldige, {len(reelle)} i ekte serie, {len(i_prod)} i prod. '
             f'Skriptets egen typing: {egne[0]} Test-Norge, {egne[1]} Dolly-serien, {egne[2]} ugyldige'
             f'{" — stemmer" if egne == (testnorge, len(syntetiske) - testnorge, ugyldige) else " — AVVIK fra Dolly"}.']
    if reelle or i_prod:
        deler.append(f'**{len(reelle)} nummer i ekte serie / {len(i_prod)} i prod skal ikke stå i denne lista — sjekk klassifiseringen.**')
    if mangler:
        deler.append(f'{len(mangler)} av de ikke-reelle numrene mangler i nedlastingen.')
    if ekstra:
        deler.append(f'{len(ekstra)} numre i nedlastingen står ikke i lista.')
    if not (reelle or i_prod or mangler or ekstra):
        deler.append('Alle numrene i lista er kontrollert; ingen er i ekte serie eller i prod.')
    return ' '.join(deler)


def skriv_ikke_reelle(s: Sveip, beslutninger):
    per_repo, per_type = ikke_reelle(s, beslutninger)
    navn = {'ugyldig': 'ugyldig kontrollsiffer/dato', 'tnr': 'Test-Norge (måned +80)', 'dnr-and-tnr': 'Test-Norge, d-nummer',
            'hnr': 'Dolly-serien (måned +40)', 'dnr-and-hnr': 'Dolly-serien, d-nummer'}
    ut = [f'# Ikke-reelle 11-sifrede numre i sveipet {s.dato}\n',
          'Numre som ikke kan være et fødselsnummer eller d-nummer for en person: ugyldig kontrollsiffer eller dato, '
          'Test-Norge-serien (måned 81–92) eller Dolly-serien (måned 41–52). De er ikke personopplysninger og listes '
          'derfor med verdi. Kontroll: lim lista inn i Dollys identvalidator '
          '(https://dolly.ekstern.dev.nav.no/identvalidator, adskilt med komma) — alle skal komme ut som syntetiske eller ugyldige, ingen i ekte serie. '
          'Numre i ekte serie står ikke her; de er funn i `baselinebevis.md`.\n']
    for repo in sorted(per_repo):
        ut.append(f'## {repo}\n')
        for typ in IKKE_REELLE_TYPER:
            verdier = sorted(per_repo[repo][typ])
            if not verdier:
                continue
            ut.append(f'{navn[typ]} — {len(verdier)} unike:\n')
            ut.append('```\n' + ','.join(verdier) + '\n```\n')
    alle = set().union(*per_type.values()) if per_type else set()
    ut.append(f'## Alle repoer samlet — {len(alle)} unike\n')
    ut.append('```\n' + ','.join(sorted(alle)) + '\n```\n')
    ut.append('## Kontroll i Dollys identvalidator\n')
    ut.append(dolly_kontroll(s, per_type) + '\n')
    (s.ut / 'ikke-reelle-numre.md').write_text('\n'.join(ut), encoding='utf-8')


def skriv_bevis(s: Sveip, beslutninger, per_nokkel, manuelle):
    per_repo = defaultdict(Counter)
    for t, _, _ in beslutninger:
        per_repo[t['RepositoryName']][per_nokkel[nokkel(t)]] += 1
    tot = Counter()
    for c in per_repo.values():
        tot.update(c)

    # Anonyme etiketter per unik verdi (på tvers av repoer), så leseren ser gjenbruk uten å se verdien
    violations = [t for t, _, _ in beslutninger if per_nokkel[nokkel(t)] == VIOLATION]
    etikett = {}
    for t in violations:
        v = str(t['Secret'])
        prefiks = 'F' if t['RuleID'] == 'off-id' else 'I'
        if (t['RuleID'], v) not in etikett:
            etikett[(t['RuleID'], v)] = f"{prefiks}{sum(1 for k in etikett if k[0] == t['RuleID']) + 1}"
    opp = {}
    for _, v in etikett:
        for repo in sorted({t['RepositoryName'] for t in violations if str(t['Secret']) == v}):
            commits = {t['Commit'] for t in violations if str(t['Secret']) == v and t['RepositoryName'] == repo}
            opp[(repo, v)] = oppfolging(s, repo, v, commits)

    def typenavn(t):
        return 'Fødselsnummer' if t['RuleID'] == 'off-id' else 'Nav-ident' if t['RuleID'] == 'nav-ident' else t['RuleID']

    def lenke(t):
        sti = quote(str(t['File']), safe='/')
        return f"[{t['Commit'][:7]}](https://github.com/navikt/{t['RepositoryName']}/blob/{t['Commit']}/{sti}#L{t['StartLine']})"

    def scope(t):
        return 'test' if er_teststi(t['File']) else 'prod'

    def sortnokkel(t):
        return (t['RepositoryName'], t['File'], s.commitdato(t), int(t['StartLine'] or 0))

    def okonomi(t):
        # Økonomi-spørsmålet gjelder bare produksjonskode; personopplysning-spørsmålet (neste kolonne) gjelder alle
        return '' if scope(t) == 'prod' else '– (testkode)'

    i_head = [t for t in violations if opp[(t['RepositoryName'], str(t['Secret']))]['i_head']]
    fjernet = [t for t in violations if not opp[(t['RepositoryName'], str(t['Secret']))]['i_head']]

    def telling(rader):
        fnr = [t for t in rader if t['RuleID'] == 'off-id']
        idn = [t for t in rader if t['RuleID'] == 'nav-ident']
        fnr_v = len(set(str(t['Secret']) for t in fnr))
        idn_v = len(set(str(t['Secret']) for t in idn))
        deler = []
        if fnr:
            deler.append(f'{len(fnr)} fødselsnummer-forekomster ({fnr_v} unike verdier)')
        if idn:
            deler.append(f'{len(idn)} Nav-ident-forekomster ({idn_v} unike)')
        andre = len(rader) - len(fnr) - len(idn)
        if andre:
            deler.append(f'{andre} andre')
        return f'{len(rader)} forekomster: ' + ', '.join(deler) if rader else '0'

    # Ikke-reelle numre
    _, per_type = ikke_reelle(s, beslutninger)
    alle_ikke_reelle = set().union(*per_type.values()) if per_type else set()
    dolly = dolly_kontroll(s, per_type)
    usikre = [(t, k) for t, status, k in beslutninger if per_nokkel[nokkel(t)] == UNSURE]
    cm = commitmelding_treff(s)
    repoer = s.repoer()
    commits = {r: (int(s.git(r, 'rev-list', '--count', '--all').strip() or 0),
                   int(s.git(r, 'rev-list', '--count', 'HEAD').strip() or 0)) for r in repoer}
    alle_commits = sum(a for a, _ in commits.values())
    main_commits = sum(m for _, m in commits.values())

    ut = [f'# Hemmelighetssveip av repoene i Team Tiltakspenger — baselinebevis {s.dato}\n']
    ut.append('## Sammendrag\n')
    ut.append(f'Hele git-historikken (alle refs) i {len(repoer)} repoer ble sveipet {s.dato} med navikt/gitleaks-wrapper '
              '(gitleaks + trufflehog, Navs regler for fødselsnummer, Nav-ident og jobb-e-post). Hvert treff er klassifisert '
              'maskinelt etter `kriterier.md`; beslutningen per treff står i `begrunnelser.csv`. Verdier gjengis ikke — funn '
              'identifiseres med repo, commit, fil og linje, og etikettene F1…/I1… viser hvor samme verdi går igjen.\n')
    ut.append('| | |')
    ut.append('|---|---|')
    ut.append(f'| Skannet | {len(repoer)} repoer, {alle_commits} commits (alle refs), {len(beslutninger)} treff |')
    ut.append('| Verktøy | gitleaks + trufflehog via navikt/gitleaks-wrapper, versjoner og digester under «Revisjonsspor» |')
    ut.append(f'| 🔴 Må byttes ut — fortsatt i HEAD | {telling(i_head)} |')
    ut.append(f'| 🟡 Fjernet fra HEAD — bare i historikken | {telling(fjernet)} |')
    ut.append(f'| 🟢 Ikke funn | {tot[OK]} treff ok etter kriteriene; {len(alle_ikke_reelle)} ikke-reelle numre kontrollert i Dolly |')
    ut.append(f'| Aktive hemmeligheter (nøkler, passord utenfor lokal utvikling) | ingen |')
    ut.append(f'| Uavgjort | {len(usikre)} |\n')
    felles = sorted({etikett[(t['RuleID'], str(t['Secret']))] for t in i_head} &
                    {etikett[(t['RuleID'], str(t['Secret']))] for t in fjernet}, key=lambda e: (e[0], int(e[1:])))
    if felles:
        ut.append(f'Etikettene telles per gruppe; {", ".join(felles)} står i begge fordi samme verdi er byttet i ett repo og '
                  'fortsatt ligger i et annet.\n')

    # 🔴
    ut.append('## 🔴 Må byttes ut — verdier som fortsatt ligger i HEAD\n')
    ut.append('Byttes til åpenbart fiktive verdier (99999999999-stil, Z-ident) i en vanlig commit. Vurderingskolonnene fylles av '
              'en utvikler: «Kan ha endret økonomien?» gjelder bare produksjonskode (vedtak, beregning, utbetaling); '
              '«Personopplysning sammen med annet?» gjelder alle — finnes det navn, relasjon eller sak sammen med verdien?\n')
    if i_head:
        ut.append('| Type | Repo | Fil:linje | Scope | Etikett | Lagt til | Status | Kan ha endret økonomien? | Personopplysning sammen med annet? |')
        ut.append('|---|---|---|---|---|---|---|---|---|')
        for t in sorted(i_head, key=sortnokkel):
            v = str(t['Secret'])
            ut.append(f"| {typenavn(t)} | {t['RepositoryName']} | `{celle(t['File'])}`:{t['StartLine']} | {scope(t)} | {etikett[(t['RuleID'], v)]} | "
                      f"{lenke(t)} {s.commitdato(t)} | {opp[(t['RepositoryName'], v)]['tekst']} | {okonomi(t)} |  |")
        ut.append('')
    else:
        ut.append('Ingen.\n')

    # 🟡
    ut.append('## 🟡 Fjernet fra HEAD — ligger i historikken og i pull requests\n')
    ut.append('Ingen kodeendring gjenstår. Verdiene er fortsatt lesbare på GitHub via commit-URL-en og via pull requestene i '
              '«Synlig via»-kolonnen; se beslutningen under. Vurderingskolonnene gjelder også her: en verdi i produksjonskode '
              'kan ha påvirket økonomien mens den lå der.\n')
    if fjernet:
        ut.append('| Type | Repo | Fil:linje | Scope | Etikett | Lagt til | Fjernet | Synlig via | Kan ha endret økonomien? | Personopplysning sammen med annet? |')
        ut.append('|---|---|---|---|---|---|---|---|---|---|')
        for t in sorted(fjernet, key=sortnokkel):
            v = str(t['Secret'])
            pr = pr_oppslag(s, t['RepositoryName'], t['Commit'])
            synlig = 'commit-URL' + (f', PR {pr}' if pr and not pr.startswith('ikke') else ' (direkte push, ingen PR)' if pr == '' else f' ({pr})')
            ut.append(f"| {typenavn(t)} | {t['RepositoryName']} | `{celle(t['File'])}`:{t['StartLine']} | {scope(t)} | {etikett[(t['RuleID'], v)]} | "
                      f"{lenke(t)} {s.commitdato(t)} | {opp[(t['RepositoryName'], v)]['tekst']} | {synlig} | {okonomi(t)} |  |")
        ut.append('')
    else:
        ut.append('Ingen.\n')

    # Beslutning
    ut.append('## Beslutning: historikken skrives ikke om\n')
    ut.append('En commit som er fjernet fra main er fortsatt tilgjengelig på GitHub. GitHubs egen veiledning '
              '([Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)) '
              'sier at etter en omskriving med force-push «the commits with sensitive data may still be accessible elsewhere: in any clones or forks '
              'of your repository, directly via their SHA-1 hashes in cached views on GitHub, through any pull requests that reference them», '
              'og at full fjerning krever at GitHub Support «dereference or delete any affected PRs, run a garbage collection on the server, '
              'remove cached views». Omskriving av main gjør i tillegg alle kloner og åpne grener ugyldige og bryter koblingen mellom '
              'deploy-kjedene i nda og commit-SHA-ene de peker på.\n')
    ut.append('Teamet bytter derfor verdiene i HEAD og lar historikken stå. Grunnlaget: et fødselsnummer uten navn, relasjon eller sak '
              'knyttet til seg er ikke en personopplysning, og vurderingen gjøres per forekomst i kolonnene over; de forekomstene som '
              'sammen med annet utgjør en personopplysning, tas videre til personvernombudet av teamet. Skulle en slik vurdering ende med at '
              'historikken må renses, er framgangsmåten `git filter-repo` + force-push + sak til GitHub Support per repo, og kolonnen '
              '«Synlig via» sier hvilke pull requests saken må omfatte.\n')

    # 🟢
    ut.append('## 🟢 Ikke funn\n')
    ut.append(f'{tot[OK]} treff er ok etter kriteriene i `kriterier.md`:\n')
    per_krit = Counter()
    for t, status, krit in beslutninger:
        if per_nokkel[nokkel(t)] == OK:
            per_krit[(t['RuleID'], krit)] += 1
    ut.append('| Regel | Kriterium | Treff |')
    ut.append('|---|---|---|')
    for (regel, krit), n in sorted(per_krit.items(), key=lambda kv: -kv[1]):
        ut.append(f'| {regel} | `{krit}` | {n} |')
    ut.append('')
    ut.append(f'**Ikke-reelle 11-sifre ({len(alle_ikke_reelle)} unike):** ugyldig kontrollsiffer/dato, Test-Norge-serien (måned 81–92) eller '
              'Dolly-serien (måned 41–52) — kan aldri være et fødselsnummer for en person. De står med verdi i `ikke-reelle-numre.md`. '
              f'Kontroll i Dollys identvalidator: {dolly}\n')
    if cm:
        ut.append('**Treff i commit-meldinger** (trufflehog, ingen filreferanse — utenfor wrapperens review-modell, vurdert manuelt):\n')
        ut.append('| Repo | Detektor | Treff | Vurdering |')
        ut.append('|---|---|---|---|')
        for (repo, det), n in sorted(cm.items()):
            vurd = 'Snyks prosjekt-ID i lenka i Snyks egne oppgraderings-PR-meldinger — ikke en nøkkel' if det == 'SnykKey' else 'ikke vurdert'
            ut.append(f'| {repo} | {det} | {n} | {vurd} |')
        ut.append('')

    # Uavgjort / manuelt
    if usikre:
        ut.append('## Til menneskelig avgjørelse (unsure)\n')
        ut.append('Avgjøres i wrapperen med `python3 run.py review --status-filter unsure`; avgjørelsen beholdes ved neste kjøring av skriptet.\n')
        ut.append('| Repo | Regel | Kriterium | Commit | Fil | Linje |')
        ut.append('|---|---|---|---|---|---|')
        for t, k in usikre:
            ut.append(f"| {t['RepositoryName']} | {t['RuleID']} | {k} | {lenke(t)} | `{celle(t['File'])}` | {t['StartLine']} |")
        ut.append('')
    if manuelle:
        ut.append('## Manuelle avgjørelser i review.json som avviker fra reglene\n')
        ut.append('| Nøkkel | Manuell status | Regelstatus |')
        ut.append('|---|---|---|')
        for n, (man, regel) in sorted(manuelle.items()):
            ut.append(f'| `{n}` | {man} | {regel} |')
        ut.append('')

    # Revisjonsspor
    ut.append('## Revisjonsspor\n')
    ut += kjoringsbevis(s, len(beslutninger))
    ut.append('')
    ut.append('| Repo | Commits (alle refs / main) | HEAD ved sveip | Treff | ok | funn | unsure |')
    ut.append('|---|---|---|---|---|---|---|')
    for repo in repoer:
        alle, main = commits[repo]
        head = s.git(repo, 'rev-parse', '--short', 'HEAD').strip()
        c = per_repo[repo]
        if c[VIOLATION]:
            regler = Counter(typenavn(t) for t in violations if t['RepositoryName'] == repo)
            funn = f"{c[VIOLATION]} ({', '.join(f'{r} {n}' for r, n in sorted(regler.items()))})"
        else:
            funn = '0'
        ut.append(f'| {repo} | {alle} / {main} | `{head}` | {sum(c.values())} | {c[OK]} | {funn} | {c[UNSURE]} |')
    ut.append(f'| **Sum** | **{alle_commits} / {main_commits}** | | **{sum(tot.values())}** | **{tot[OK]}** | **{tot[VIOLATION]}** | **{tot[UNSURE]}** |\n')
    ut.append(f'Tallene er per treff og er de samme som wrapperens `run.py report` viser ({len(per_nokkel)} review-nøkler; flere treff på '
              'samme linje deler nøkkel). «HEAD ved sveip» er klonens main-commit da sveipet ble tatt — «fortsatt i HEAD» over er målt mot den. '
              'Bildebevis per repo: `python3 run.py report --repository-filter <repo>` i wrapperen. Filer i denne mappa: `kriterier.md` (reglene som '
              'gjaldt), `begrunnelser.csv` (én rad per treff), `rapport.txt` (wrapperens rapport, Todo: 0), `ikke-reelle-numre.md`, '
              '`identvalidering.csv` (Dollys nedlasting), `pr-oppslag.json` (GitHub-svarene bak «Synlig via»), `review.json`.\n')

    (s.ut / 'baselinebevis.md').write_text('\n'.join(ut), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--wrapper', default=os.environ.get('GITLEAKS_WRAPPER', str(Path.home() / 'dev/nav/gitleaks-wrapper')),
                   help='sti til gitleaks-wrapper (standard: $GITLEAKS_WRAPPER eller ~/dev/nav/gitleaks-wrapper)')
    p.add_argument('--dato', help='sveipdato YYYY-MM-DD (standard: rapportfilenes tidsstempel)')
    p.add_argument('--write', action='store_true', help='skriv review.json i wrapperen og reports/sveip-<dato>/ her')
    p.add_argument('--regler-vinner', action='store_true', help='se bort fra manuelle avgjørelser i eksisterende review.json')
    a = p.parse_args()
    if a.dato and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', a.dato):
        p.error('--dato må være YYYY-MM-DD')
    if not KRITERIER.exists():
        sys.exit(f'{KRITERIER} mangler — kriteriene skal finnes før noe klassifiseres')

    s = Sveip(Path(a.wrapper).expanduser().resolve(), a.dato)
    beslutninger, per_nokkel, manuelle, eksisterende = kjor(s, a.regler_vinner)
    skriv_oversikt(beslutninger, per_nokkel, manuelle)
    if a.write:
        skriv_alt(s, beslutninger, per_nokkel, manuelle, eksisterende)
    else:
        print(f'\nTørrkjøring. --write skriver {s.review} og {s.ut}/')


if __name__ == '__main__':
    main()
