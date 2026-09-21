"""Felles Maven-oppslag for nyeste-versjoner.py og app-utdatert.py.

«Nyeste versjon» følger versjonspolicyen i SKILL.md: høyeste stabile versjon som er ute av cooldown.
Publiseringstiden er Last-Modified på POM-en. Ukjent alder regnes som ikke tillatt.
"""
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

COOLDOWN = timedelta(hours=168)
# Nav-unntaket: egne Maven-grupper oppdateres uten cooldown.
NAV_GRUPPER = ("com.github.navikt", "no.nav")
BASER = (
    "https://repo1.maven.org/maven2/",
    "https://plugins.gradle.org/m2/",
    "https://packages.confluent.io/maven/",
    "https://github-package-registry-mirror.gc.nav.no/cached/maven-release/",
)
UNSTABLE = re.compile(r"(?i)(alpha|beta|rc\d*|m\d+|snapshot|ccs|preview|-ea|dev|cr\d*|pre|eap|b\d+$)")
# Hvor mange kandidater i cooldown oppslaget sjekker før det gir opp.
MAKS_KANDIDATER = 15


@dataclass
class Oppslag:
    versjon: str | None = None
    publisert: datetime | None = None
    # Nyere versjoner som ikke er tillatt ennå: (versjon, tidligste tillatte tidspunkt eller None ved ukjent alder).
    holdt_utenfor: list[tuple[str, datetime | None]] = field(default_factory=list)


def parse(v: str):
    # Tall sorterer over tekst, så «2.1.0git» havner under «2.1.1».
    return [((1, int(p)) if p.isdigit() else (0, p)) for p in re.split(r"[.\-_]", v)]


def fetch(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return r.read().decode()
    except Exception:
        return None


def hent_publiseringstid(base: str, g: str, a: str, v: str) -> datetime | None:
    url = f"{base}{g.replace('.', '/')}/{a}/{v}/{a}-{v}.pom"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=25) as r:
            return parsedate_to_datetime(r.headers["Last-Modified"]).astimezone(timezone.utc)
    except Exception:
        return None


def nyeste(module: str, current: str) -> Oppslag | None:
    """Finner høyeste stabile og tillatte versjon over `current`.

    Gir `current` når alle nyere kandidater er holdt utenfor, og None når koordinaten ikke finnes i noen base.
    """
    g, a = module.split(":")
    nå = datetime.now(timezone.utc)
    for base in BASER:
        xml = fetch(f"{base}{g.replace('.', '/')}/{a}/maven-metadata.xml")
        if not xml:
            continue
        kandidater = sorted(
            {
                v
                for v in re.findall(r"<version>([^<]+)</version>", xml)
                if v[0].isdigit()
                and not UNSTABLE.search(v.replace(".Final", "").replace(".RELEASE", ""))
                and parse(v) > parse(current)
            },
            key=parse,
            reverse=True,
        )
        oppslag = Oppslag()
        for v in kandidater[:MAKS_KANDIDATER]:
            tid = hent_publiseringstid(base, g, a, v)
            if g.startswith(NAV_GRUPPER) or (tid and nå - tid >= COOLDOWN):
                oppslag.versjon, oppslag.publisert = v, tid
                return oppslag
            oppslag.holdt_utenfor.append((v, tid + COOLDOWN if tid else None))
        oppslag.versjon = current
        return oppslag
    return None


def hopp(cur: str, new: str) -> str:
    c = [p for p in re.split(r"[.\-]", cur) if p.isdigit()]
    n = [p for p in re.split(r"[.\-]", new) if p.isdigit()]
    if cur == new:
        return "-"
    if c[:1] != n[:1]:
        return "MAJOR"
    if c[:2] != n[:2]:
        return "minor"
    return "patch"


def utc(tid: datetime | None) -> str:
    return tid.strftime("%Y-%m-%d %H:%MZ") if tid else "ukjent"


def holdt_utenfor_tekst(oppslag: Oppslag) -> str:
    return ", ".join(
        f"{v} (tidligst {utc(tid)})" if tid else f"{v} (ukjent alder)" for v, tid in oppslag.holdt_utenfor
    )
