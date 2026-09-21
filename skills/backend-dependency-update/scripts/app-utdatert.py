#!/usr/bin/env python3
"""Finner direkte deklarerte Maven-koordinater i et build.gradle.kts, løser $variabler, og slår opp nyeste versjon.

Nyeste versjon er høyeste stabile versjon ute av cooldown, se maven_oppslag.py.

Bruk: app-utdatert.py <sti/til/build.gradle.kts> [<flere>...]
Skriver én markdown-tabell per fil. Bare koordinater med nyere versjon listes, også når den er holdt utenfor.
"""
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True

from maven_oppslag import holdt_utenfor_tekst, hopp, nyeste, utc

SKIP_GROUPS = ("com.github.navikt.tiltakspenger-libs", "org.jetbrains.kotlin:kotlin-bom")


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
    print("| modul | variabel | nå | nyeste | publisert UTC | hopp | holdt utenfor |")
    print("|---|---|---|---|---|---|---|")

    def job(c):
        module, ver, var = c
        return (module, var, ver, nyeste(module, ver))

    with ThreadPoolExecutor(max_workers=12) as ex:
        rows = list(ex.map(job, sorted(coords)))
    for module, var, ver, oppslag in rows:
        if oppslag is None:
            print(f"| {module} | {var} | {ver} | ? | | ikke funnet | |")
        elif oppslag.versjon != ver or oppslag.holdt_utenfor:
            new = oppslag.versjon
            tid = utc(oppslag.publisert) if new != ver else ""
            print(f"| {module} | {var} | {ver} | {new} | {tid} | {hopp(ver, new)} | {holdt_utenfor_tekst(oppslag)} |")
