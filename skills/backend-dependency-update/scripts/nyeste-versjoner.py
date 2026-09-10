#!/usr/bin/env python3
"""Slår opp nyeste stabile versjon for hver nøkkel i gradle/libs.versions.toml.

Kilder: Maven Central (repo1), Gradle Plugin Portal (plugins.gradle.org/m2), services.gradle.org for wrapperen.
Kjøres fra libs-rota. Skriver en markdown-tabell til stdout.
"""
import re
import sys
import tomllib
import urllib.request
from concurrent.futures import ThreadPoolExecutor

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
rep.setdefault("ktlint", "com.pinterest.ktlint:ktlint-cli")
rep.setdefault("kotlin", "org.jetbrains.kotlin:kotlin-gradle-plugin")

UNSTABLE = re.compile(r"(?i)(alpha|beta|rc|m\d|snapshot|ccs|preview|ea|dev|cr|pre|eap|b\d+$)")


def parse(v: str):
    parts = re.split(r"[.\-_]", v)
    out = []
    for p in parts:
        if p.isdigit():
            out.append((0, int(p)))
        else:
            out.append((1, p))
    return out


def fetch(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return r.read().decode()
    except Exception:
        return None


def latest_for(module: str):
    g, a = module.split(":")
    for base in ("https://repo1.maven.org/maven2/", "https://plugins.gradle.org/m2/"):
        xml = fetch(f"{base}{g.replace('.', '/')}/{a}/maven-metadata.xml")
        if not xml:
            continue
        vs = re.findall(r"<version>([^<]+)</version>", xml)
        stable = [v for v in vs if not UNSTABLE.search(v.replace(".Final", ""))]
        if not stable:
            return None, base
        return max(stable, key=parse), base
    return None, None


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


rows = []


def job(key):
    cur = versions[key]
    module = rep.get(key)
    if not module:
        return (key, cur, "?", "(ingen modul)", "")
    new, kilde = latest_for(module)
    if new is None:
        return (key, cur, "?", module, "ikke funnet")
    return (key, cur, new, module, hopp(cur, new))


with ThreadPoolExecutor(max_workers=12) as ex:
    rows = list(ex.map(job, sorted(versions)))

print("| nøkkel | nå | nyeste stabil | hopp | modul |")
print("|---|---|---|---|---|")
for key, cur, new, module, h in rows:
    print(f"| {key} | {cur} | {new} | {h} | {module} |")

gw = fetch("https://services.gradle.org/versions/current")
print()
print("Gradle current:", gw.strip() if gw else "ukjent")
