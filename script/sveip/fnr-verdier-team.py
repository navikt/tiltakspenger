#!/usr/bin/env python3
"""Kommaseparert liste av ellevesifre fra en fnr-team.py-kjøring, med verdier, til Dollys identvalidator.

Skriptet inneholder ingen verdier selv; verdiene hentes fra klonene når det kjøres, og går rett til
utklippstavlen (pbcopy) eller til fila du oppgir. Terminalen får bare antall.

    ./script/sveip/fnr-verdier-team.py ~/dev/nav/team-tiltak --gruppe gyldig-head
    ./script/sveip/fnr-verdier-team.py ~/dev/nav/team-tiltak --gruppe gyldig-historikk --del 1/4
    ./script/sveip/fnr-verdier-team.py ~/dev/nav/komet --gruppe syntetisk

Grupper:
  gyldig-head       — gyldig nummerserie som fortsatt finnes i HEAD. CSV-en bærer aldri verdien, så den
                      hentes fra klonen med `git show <commit>:<fil>` og linjenummeret, og valideres på
                      nytt med samme regler som fnr-team.py (plassholdere ut, kun fnr/dnr med).
  gyldig-historikk  — som over, for verdier som kun finnes i historikken
  syntetisk         — radene med gyldig_serie=nei; verdien står i CSV-en. Kontroll: Dolly skal svare
                      erSyntetisk=true eller erGyldig=false, og erIProd tom.

`--del K/N` deler lista i N like deler og gir del K, hvis validatoren ikke tar alt på én gang.
Lim inn i https://dolly.ekstern.dev.nav.no/identvalidator (krever innlogging), last ned identvalidering.csv
og legg den som <teammappe>/identvalidering-<gruppe>-<dato>[-K].csv.
Reelle numre kjennes på erSyntetisk=false; erIProd er tom for syntetiske og ugyldige.
"""
import argparse
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

HER = Path(__file__).resolve().parent
sys.path.insert(0, str(HER))
from klassifiser import plassholder_sifre  # noqa: E402

ELLEVE = re.compile(r'(?<!\d)\d{11}(?!\d)')
GYLDIG_SERIE_TYPER = ('fnr', 'dnr')


def finn_validate(wrapper: Path):
    """Samme fnrvalidator-logikk som fnr-team.py og klassifiser.py henter fra wrapperen."""
    if not (wrapper / 'validate.py').exists():
        sys.exit(f'fant ikke validate.py i {wrapper} (bruk --wrapper eller GITLEAKS_WRAPPER)')
    sys.path.append(str(wrapper))
    from validate import validate
    return validate


def git_fil(repo: Path, commit: str, fil: str) -> list[str]:
    """Filversjonen som linjer. Kalles én gang per (repo, commit, fil): team-tiltak har 116 021
    linjeoppslag, men bare 321 filversjoner."""
    if not re.fullmatch(r'[0-9a-f]{7,40}', commit):
        return []
    r = subprocess.run(['git', '-C', str(repo), 'show', f'{commit}:{fil}'],
                       capture_output=True, text=True, errors='replace')
    return r.stdout.split('\n') if r.returncode == 0 else []


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('teammappe')
    p.add_argument('--gruppe', choices=['gyldig-head', 'gyldig-historikk', 'syntetisk'], required=True)
    p.add_argument('--dato', default='2026-09-07')
    p.add_argument('--wrapper', default=os.environ.get('GITLEAKS_WRAPPER', str(Path.home() / 'dev/nav/gitleaks-wrapper')))
    p.add_argument('--del', dest='del_', help='K/N: del K av N')
    p.add_argument('--ut', help='skriv til fil i stedet for utklippstavlen')
    a = p.parse_args()

    mappe = Path(a.teammappe).expanduser().resolve()
    csvfil = mappe / f'fnr-{a.dato}.csv'
    if not csvfil.exists():
        sys.exit(f'finner ikke {csvfil}')
    rader = list(csv.DictReader(open(csvfil, encoding='utf-8')))

    verdier = []
    if a.gruppe == 'syntetisk':
        verdier = [r['verdi'] for r in rader if r['gyldig_serie'] == 'nei' and r['verdi']]
    else:
        validate = finn_validate(Path(a.wrapper).expanduser().resolve())
        vil_head = 'ja' if a.gruppe == 'gyldig-head' else 'nei'
        linjer_per_fil: dict[tuple, set[int]] = {}
        for r in rader:
            if r['gyldig_serie'] == 'ja' and r['i_head'] == vil_head:
                linjer_per_fil.setdefault((r['repo'], r['commit'], r['fil']), set()).add(int(r['linje']))
        uløst = 0
        for (repo, commit, fil), linjenumre in sorted(linjer_per_fil.items()):
            if '[11 siffer]' in fil:
                uløst += len(linjenumre)  # filnavnet er selv verdien og er maskert i CSV-en
                continue
            innhold = git_fil(mappe / repo, commit, fil)
            for linje in sorted(linjenumre):
                tekst = innhold[linje - 1] if 0 < linje <= len(innhold) else ''
                treff = 0
                for kandidat in ELLEVE.findall(tekst):
                    if plassholder_sifre(kandidat):
                        continue
                    resultat = validate(kandidat)
                    if resultat.status == 'valid' and resultat.type in GYLDIG_SERIE_TYPER:
                        verdier.append(kandidat)
                        treff += 1
                if not treff:
                    uløst += 1
        if uløst:
            print(f'{uløst} rader ga ingen verdi (maskert filnavn, eller linja finnes ikke i commiten)')

    unike = sorted(set(verdier))
    if a.del_:
        k, n = (int(x) for x in a.del_.split('/'))
        if not 1 <= k <= n:
            sys.exit(f'--del må være K/N med 1 ≤ K ≤ N, fikk {a.del_}')
        størrelse = -(-len(unike) // n)
        unike = unike[(k - 1) * størrelse:k * størrelse]
    tekst = ','.join(unike)
    if a.ut:
        Path(a.ut).write_text(tekst + '\n')
        print(f'{len(unike)} unike verdier skrevet til {a.ut}')
    else:
        subprocess.run(['pbcopy'], input=tekst, text=True, check=True)
        print(f'{len(unike)} unike verdier ligger på utklippstavlen')


if __name__ == '__main__':
    main()
