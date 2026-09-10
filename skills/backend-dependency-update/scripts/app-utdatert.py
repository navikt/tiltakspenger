#!/usr/bin/env python3
"""Finner direkte deklarerte Maven-koordinater i et build.gradle.kts, løser $variabler, og slår opp nyeste stabile.

Bruk: app-utdatert.py <sti/til/build.gradle.kts> [<flere>...]
Skriver én markdown-tabell per fil. Kun avvik (nå != nyeste) listes.
"""
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UNSTABLE = re.compile(r"(?i)(alpha|beta|rc\d*|m\d+|snapshot|ccs|preview|-ea|dev|cr\d*|pre|eap|b\d+$)")
SKIP_GROUPS = ("com.github.navikt.tiltakspenger-libs", "org.jetbrains.kotlin:kotlin-bom")


def parse(v):
    return [((0, int(p)) if p.isdigit() else (1, p)) for p in re.split(r"[.\-_]", v)]


def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return r.read().decode()
    except Exception:
        return None


def latest(module, current):
    g, a = module.split(":")
    bases = ["https://repo1.maven.org/maven2/", "https://plugins.gradle.org/m2/",
             "https://packages.confluent.io/maven/",
             "https://github-package-registry-mirror.gc.nav.no/cached/maven-release/"]
    for base in bases:
        xml = fetch(f"{base}{g.replace('.', '/')}/{a}/maven-metadata.xml")
        if not xml:
            continue
        vs = re.findall(r"<version>([^<]+)</version>", xml)
        # Samme linje som nå for ktor (låst 3.4) og netty 4.1
        if g == "io.ktor":
            vs = [v for v in vs if v.startswith("3.4.")]
        if module == "io.netty:netty-bom" and current.startswith("4.1."):
            vs = [v for v in vs if v.startswith("4.1.")]
        stable = [v for v in vs if not UNSTABLE.search(v.replace(".Final", "").replace(".RELEASE", ""))]
        if not stable:
            return None
        return max(stable, key=parse)
    return None


def hopp(cur, new):
    c = [p for p in re.split(r"[.\-]", cur) if p.isdigit()]
    n = [p for p in re.split(r"[.\-]", new) if p.isdigit()]
    if cur == new:
        return "-"
    if c[:1] != n[:1]:
        return "MAJOR"
    if c[:2] != n[:2]:
        return "minor"
    return "patch"


for path in sys.argv[1:]:
    txt = open(path).read()
    vals = dict(re.findall(r'val\s+(\w+)\s*=\s*"([^"]+)"', txt))
    coords = set()
    for g, a, v in re.findall(r'"([A-Za-z0-9_.\-]+):([A-Za-z0-9_.\-]+):([^"]+)"', txt):
        if any(g.startswith(s) or f"{g}:{a}".startswith(s) for s in SKIP_GROUPS):
            continue
        m = re.fullmatch(r"\$\{?(\w+)\}?", v)
        var = m.group(1) if m else None
        ver = vals.get(var, v) if var else v
        if not re.match(r"^[0-9]", ver):
            continue
        coords.add((f"{g}:{a}", ver, var or ""))
    # plugins: id("x") version "y"
    for pid, v in re.findall(r'id\("([^"]+)"\)\s+version\s+"([^"]+)"', txt):
        coords.add((f"{pid}:{pid}.gradle.plugin", v, "(plugin)"))
    print(f"\n## {path}")
    print("| modul | variabel | nå | nyeste | hopp |")
    print("|---|---|---|---|---|")

    def job(c):
        module, ver, var = c
        new = latest(module, ver)
        return (module, var, ver, new)

    with ThreadPoolExecutor(max_workers=12) as ex:
        rows = list(ex.map(job, sorted(coords)))
    for module, var, ver, new in rows:
        if new is None:
            print(f"| {module} | {var} | {ver} | ? | ikke funnet |")
        elif new != ver:
            print(f"| {module} | {var} | {ver} | {new} | {hopp(ver, new)} |")
