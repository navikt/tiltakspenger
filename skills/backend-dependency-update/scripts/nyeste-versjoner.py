#!/usr/bin/env python3
"""Slår opp nyeste versjon for hver nøkkel i gradle/libs.versions.toml.

Nyeste versjon er høyeste stabile versjon ute av cooldown, se maven_oppslag.py. services.gradle.org gir wrapperen.
Kjøres fra libs-rota. Skriver en markdown-tabell til stdout.
"""
import json
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True

from maven_oppslag import fetch, holdt_utenfor_tekst, hopp, nyeste, utc

TOML = sys.argv[1] if len(sys.argv) > 1 else "gradle/libs.versions.toml"
data = tomllib.load(open(TOML, "rb"))
versions = data["versions"]
libs = data["libraries"]

# Representativ modul per versjonsnøkkel (første bibliotek som refererer nøkkelen).
rep: dict[str, str] = {}
for name, lib in libs.items():
    v = lib.get("version")
    ref = v.get("ref") if isinstance(v, dict) else None
    if ref and ref not in rep:
        rep[ref] = lib["module"]
# Plugins uten bibliotek i katalogen slås opp via markerartefakten.
for plugin in data.get("plugins", {}).values():
    v = plugin.get("version")
    ref = v.get("ref") if isinstance(v, dict) else None
    if ref and ref not in rep:
        rep[ref] = f"{plugin['id']}:{plugin['id']}.gradle.plugin"
rep.setdefault("ktlint", "com.pinterest.ktlint:ktlint-cli")
rep.setdefault("kotlin", "org.jetbrains.kotlin:kotlin-gradle-plugin")

rows = []


def job(key):
    cur = versions[key]
    module = rep.get(key)
    if not module:
        return (key, cur, "?", "", "", "(ingen modul)", "")
    oppslag = nyeste(module, cur)
    if oppslag is None:
        return (key, cur, "?", "", "ikke funnet", module, "")
    new = oppslag.versjon
    return (key, cur, new, utc(oppslag.publisert) if new != cur else "", hopp(cur, new), module, holdt_utenfor_tekst(oppslag))


with ThreadPoolExecutor(max_workers=12) as ex:
    rows = list(ex.map(job, sorted(versions)))

print("| nøkkel | nå | nyeste | publisert UTC | hopp | modul | holdt utenfor |")
print("|---|---|---|---|---|---|---|")
for key, cur, new, tid, h, module, utenfor in rows:
    print(f"| {key} | {cur} | {new} | {tid} | {h} | {module} | {utenfor} |")

gw = fetch("https://services.gradle.org/versions/current")
print()
if gw:
    gradle = json.loads(gw)
    print(f"Gradle current: {gradle['version']} (bygget {gradle['buildTime']})")
else:
    print("Gradle current: ukjent")
