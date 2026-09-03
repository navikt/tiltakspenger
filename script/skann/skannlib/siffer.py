"""Mod11, fødselsnummer, kontonummer og vaktene rundt dem.

Fødselsnummer (k2) og kontonummer bruker samme mod11-vekter. Modulen samler
beregningene og kontekstvaktene som skiller et frittstående 11-sifret tall fra
et versjonsnummer, en Maven-koordinat eller halen av en digest.
"""
import re

VEKTER_FNR_K1 = (3, 7, 6, 1, 8, 9, 4, 5, 2)
VEKTER_FNR_K2 = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
VEKTER_KONTO = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)

FNR_MØNSTER = re.compile(r"(?<!\d)\d{11}(?!\d)")
KONTO_MØNSTER = re.compile(r"(?<!\d)(\d{4})[.\s]?(\d{2})[.\s]?(\d{5})(?!\d)")

MAVEN_KOORDINAT = re.compile(r"^[A-Za-z][\w.-]*:[\w.-]+:[\w.-]*\d{11}[\w.-]*$")


def kontrollsiffer(siffer, vekter):
    """Beregner mod11-kontrollsifferet, eller None når resten er 1."""
    sum_ = sum(s * v for s, v in zip(siffer, vekter))
    rest = sum_ % 11
    if rest == 0:
        return 0
    if rest == 1:
        return None
    return 11 - rest


def fnr_ordning(tekst):
    """Hvilken ordning nummeret validerer etter, eller None.

    «gammel» — k1 og k2 stemmer, slik fødselsnummer har vært bygget til nå.
    «2032»   — kun k2 stemmer. Skatteetaten frigjør det første kontrollsifferet
               for å utvide nummerrommet, så fra 2032 er k2 alene fasiten.
               Dolly deler allerede ut slike numre, og en sjekk som krever k1
               er blind for dem.

    k2 bruker samme vekter som kontonummer-kontrollen. Et nummer som kun
    validerer etter 2032-ordningen har derfor ikke sterkere validering enn et
    kontonummer — det er datoformen i de fire første sifrene som skiller dem.
    """
    siffer = [int(c) for c in tekst]
    k2 = kontrollsiffer(siffer[:10], VEKTER_FNR_K2)
    if k2 is None or k2 != siffer[10]:
        return None
    k1 = kontrollsiffer(siffer[:9], VEKTER_FNR_K1)
    return "gammel" if k1 is not None and k1 == siffer[9] else "2032"


def er_gyldig_konto(tekst):
    """Sant når teksten validerer mod11 som kontonummer."""
    siffer = [int(c) for c in tekst]
    k = kontrollsiffer(siffer[:10], VEKTER_KONTO)
    return k is not None and k == siffer[10]


# Lengste måned i hvert kalendermåned-nummer. Februar får 29: et fødselsnummer
# bærer bare to sifre av årstallet, og hvilket århundre det er avgjøres av
# individnummeret — vi godtar derfor skuddårsdatoen uansett.
DAGER_I_MÅNED = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def fnr_kategori(tekst):
    """Returnerer (nivå, beskrivelse) for et gyldig fødselsnummer.

    D-nummer har 4 lagt til første siffer (dag 41–71). Måneden angir
    nummerserien: 01–12 er ekte, 41–52 er Dolly, 81–92 er Test-Norge.
    Klassifiseringen er den samme for begge ordninger.

    Datoen kontrolleres etter at både D-nummer- og serietillegget er trukket
    fra. Uten det ville 31. februar passert som fødselsdato, og mod11 alene
    slipper gjennom rundt hver ellevte slike dato.
    """
    ordning = fnr_ordning(tekst)
    if ordning is None:
        return None
    dag = int(tekst[0:2])
    if dag > 40:
        dag -= 40
        form = "D-nummer"
    else:
        form = "fødselsnummer"
    if not 1 <= dag <= 31:
        return None

    månedstall = int(tekst[2:4])
    if 1 <= månedstall <= 12:
        måned, nivå, serie = månedstall, "FUNN", "ekte nummerserie"
    elif 41 <= månedstall <= 52:
        måned, nivå, serie = månedstall - 40, "INFO", "syntetisk (Dolly)"
    elif 81 <= månedstall <= 92:
        måned, nivå, serie = månedstall - 80, "INFO", "syntetisk (Test-Norge)"
    else:
        return None
    if dag > DAGER_I_MÅNED[måned - 1]:
        return None

    if ordning == "2032":
        merke = " (2032-ordning, kan også være kontonummer)"
    else:
        merke = " (gammel ordning)"
    return nivå, f"gyldig {form}{merke}, {serie}"


def er_plassholdersekvens(tekst):
    """Sant for sekvenser som i praksis alltid er plassholdere.

    Åtte sifre på rad som er like, øker eller synker med ett — formen
    plassholdere i testdata og dokumentasjon har. Filteret er en bevisst
    støyavveining, ikke en matematisk sannhet: et gyldig nummer kan ha denne
    formen, og et par gjør det. Uten filteret kommer rundt 355 slike treff i
    flåten, og de drukner de ekte.

    Brukes kun i testkode. I prod er en plassholder like uønsket som et ekte
    nummer, og filteret er derfor koblet ut der.
    """
    like = stigende = synkende = 1
    for i in range(1, len(tekst)):
        differanse = int(tekst[i]) - int(tekst[i - 1])
        like = like + 1 if differanse == 0 else 1
        stigende = stigende + 1 if differanse == 1 else 1
        synkende = synkende + 1 if differanse == -1 else 1
        if max(like, stigende, synkende) >= 8:
            return True
    return False


def del_av_lengre_verdi(linje, start, slutt):
    """Sant når sifferrekka inngår i et større tall, en koordinat eller en id.

    Skiller versjoner, datoer, Maven-koordinater og alfanumeriske
    identifikatorer — halen av en sha256-digest i en lockfil, eller en
    `10000000000L`-literal — fra et frittstående 11-sifret tall. Koordinaten
    kjennes på formen gruppe:artefakt:versjon, så en logglinje som
    «fnr:<11 siffer>» treffer fortsatt.
    """
    if start > 0 and (linje[start - 1].isalpha() or linje[start - 1] == "_"):
        return True  # del av en id eller digest
    if slutt < len(linje) and (linje[slutt].isalpha() or linje[slutt] == "_"):
        return True
    if start >= 2 and linje[start - 1] in ".-," and linje[start - 2].isdigit():
        return True
    if slutt + 1 < len(linje) and linje[slutt] in ".-," and linje[slutt + 1].isdigit():
        return True
    venstre = start
    while venstre > 0 and (linje[venstre - 1].isalnum() or linje[venstre - 1] in ".-_:"):
        venstre -= 1
    høyre = slutt
    while høyre < len(linje) and (linje[høyre].isalnum() or linje[høyre] in ".-_:"):
        høyre += 1
    return bool(MAVEN_KOORDINAT.match(linje[venstre:høyre]))
