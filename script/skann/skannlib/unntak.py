"""Unntakslistene: innlesing, begrunnelseskrav, oppslag og statistikk.

Listene er delt i to — én for produksjonskode og én for testkode — slik at et
testunntak aldri kan skjule et funn i prod.
"""
import os
import re

# Listene hører til skriptet, ikke til repoet som skannes.
MAPPE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STANDARDFILER = {
    "prod": os.path.join(MAPPE, "skann-unntak-prod.txt"),
    "test": os.path.join(MAPPE, "skann-unntak-test.txt"),
}


class Unntak:
    """Én unntaksoppføring, med teller over antall undertrykte treff."""

    def __init__(self, scope, repo_navn, sjekk, mønster, linjenr, råtekst):
        self.scope = scope
        self.repo_navn = repo_navn
        self.sjekk = sjekk
        self.mønster = mønster
        self.linjenr = linjenr
        self.råtekst = råtekst
        self.antall = 0


def les(scope, sti, sjekker, feil):
    """Leser én unntaksliste.

    Hver oppføring krever en #-begrunnelse på linja over. En linje med bare «#»
    hører til en flerlinjes begrunnelse; en blank linje avslutter blokka.
    `feil` kalles med en melding ved ugyldig innhold.
    """
    oppføringer = []
    har_begrunnelse = False
    with open(sti, encoding="utf-8") as fh:
        for nr, linje in enumerate(fh, 1):
            renset = linje.strip()
            if not renset:
                har_begrunnelse = False
                continue
            if renset.startswith("#"):
                har_begrunnelse = har_begrunnelse or len(renset) > 1
                continue
            deler = renset.split(None, 1)
            if len(deler) != 2:
                feil(f"{sti}:{nr}: forventet «sjekk-id regex» eller "
                     f"«repo-navn/sjekk-id regex», fant «{renset}»")
            nøkkel, mønster = deler
            repo_navn, _, sjekk = nøkkel.rpartition("/")
            repo_navn = repo_navn or None
            if sjekk not in sjekker:
                feil(f"{sti}:{nr}: ukjent sjekk «{sjekk}». "
                     f"Gyldige: {', '.join(sjekker)}")
            if not har_begrunnelse:
                feil(f"{sti}:{nr}: unntaket «{renset}» mangler begrunnelse. "
                     "Legg til en #-kommentar med begrunnelse på linja over.")
            try:
                oppføringer.append(
                    Unntak(scope, repo_navn, sjekk, re.compile(mønster), nr, renset),
                )
            except re.error as årsak:
                feil(f"{sti}:{nr}: ugyldig regex «{mønster}»: {årsak}")
            har_begrunnelse = False
    return oppføringer


def dekker(oppføringer, scope, repo_navn, sjekk, sti, tekst):
    """Sant når en oppføring dekker treffet. Øker trefftelleren.

    Oppføringen må høre til filens scope, gjelde samme sjekk, og enten være en
    fellesregel eller navngi repoet.
    """
    for unntak in oppføringer:
        if unntak.scope != scope or unntak.sjekk != sjekk:
            continue
        if unntak.repo_navn is not None and unntak.repo_navn != repo_navn:
            continue
        if unntak.mønster.search(tekst) or unntak.mønster.search(f"{sti}:{tekst}"):
            unntak.antall += 1
            return True
    return False


def skriv_statistikk(oppføringer, filer, repo_navn, valgte, undertrykt, skriv):
    """Skriver statistikk per liste over brukte og ubrukte oppføringer.

    Ubrukte oppføringer er unntak for kode som ikke finnes lenger. De skal
    slettes, ellers dekker de noe nytt en dag uten at noen har bestemt det.
    """
    if not oppføringer:
        return
    skriv("")
    skriv("Unntaksstatistikk")
    for scope in ("prod", "test"):
        egne = [u for u in oppføringer if u.scope == scope]
        if not filer.get(scope):
            continue
        gjeldende = [u for u in egne
                     if u.sjekk in valgte
                     and (u.repo_navn is None or u.repo_navn == repo_navn)]
        brukte = [u for u in gjeldende if u.antall]
        ubrukte = [u for u in gjeldende if not u.antall]
        skriv(f"  [{scope}] {filer[scope]}")
        skriv(f"    {len(egne)} oppføringer, {len(gjeldende)} gjelder {repo_navn} "
              f"og de valgte sjekkene, {undertrykt.get(scope, 0)} treff undertrykt.")
        for unntak in sorted(brukte, key=lambda u: -u.antall):
            skriv(f"      {unntak.antall:>4}  {unntak.råtekst}  "
                  f"(linje {unntak.linjenr})")
        if ubrukte:
            skriv(f"    Ubrukte ({len(ubrukte)} oppføringer — kandidater for "
                  f"opprydding i {repo_navn} eller i fellesreglene):")
            for unntak in ubrukte:
                skriv(f"            {unntak.råtekst}  (linje {unntak.linjenr})")
