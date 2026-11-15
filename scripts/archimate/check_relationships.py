#!/usr/bin/env python3
"""Check that every relationship in relations.csv is allowed by ArchiMate 3.2.

The rules are read from the pinned Archi install (relationships.xml), never copied into the repo.

  python3 -I check_relationships.py <model-dir> <archi-home>

Prints every problem with the relationship ID, then a count; exits 1 if there is any problem.
"""
import csv
import glob
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def load_rules(archi_home):
    pattern = str(Path(archi_home) / "plugins" / "com.archimatetool.model_*" / "model")
    folders = sorted(glob.glob(pattern))
    if not folders:
        fail(f"Archi rules not found at {pattern} — run ./bootstrap.sh")
    folder = Path(folders[-1])
    try:
        keys = {
            k.get("char"): k.get("relationship")
            for k in ET.parse(folder / "relationships-keys.xml").getroot()
        }
        root = ET.parse(folder / "relationships.xml").getroot()
    except (OSError, ET.ParseError) as err:
        fail(f"Cannot read Archi rules in {folder}: {err} — run ./bootstrap.sh")
    rules = {
        (source.get("concept"), target.get("concept")): {keys[c] for c in target.get("relations")}
        for source in root
        for target in source
    }
    return rules, set(keys.values())


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main():
    model_dir, archi_home = Path(sys.argv[1]), sys.argv[2]
    rules, known_types = load_rules(archi_home)
    types = {row["ID"]: row["Type"] for row in read_csv(model_dir / "elements.csv")}
    relations = read_csv(model_dir / "relations.csv")
    problems = []
    for rel in relations:
        rid, rtype, src, dst = rel["ID"], rel["Type"], rel["Source"], rel["Target"]
        missing = [i for i in (src, dst) if i not in types]
        for ident in missing:
            problems.append(f"{rid}: {ident} is not in elements.csv")
        if rtype not in known_types:
            problems.append(f"{rid}: unknown relationship type {rtype}")
        if missing or rtype not in known_types:
            continue
        allowed = rules.get((types[src], types[dst]), set())
        if rtype not in allowed:
            names = ", ".join(sorted(allowed)) or "none"
            problems.append(
                f"{rid}: {rtype} is not allowed from {types[src]} ({src}) to {types[dst]} ({dst});"
                f" allowed: {names}"
            )
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    if problems:
        fail(f"relationships: {len(problems)} problem(s) in {len(relations)} checked")
    print(f"relationships: {len(relations)} checked, all allowed by ArchiMate 3.2")


main()
