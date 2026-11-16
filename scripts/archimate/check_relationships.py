#!/usr/bin/env python3
"""Check that every relationship of the exchange model is allowed by ArchiMate 3.2.

The rules are read from the pinned Archi install (relationships.xml), never copied into the repo.

  python3 -I check_relationships.py <model.xml> <archi-home>

Prints every problem with the relationship ID, then a count; exits 1 if there is any problem.
"""
import glob
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Sibling module. Added explicitly because `python3 -I` (isolated mode) leaves the script's
# own folder off sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import exchange  # noqa: E402


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def load_rules(archi_home):
    pattern = str(Path(archi_home) / "plugins" / "com.archimatetool.model_*" / "model")
    folders = sorted(glob.glob(pattern))
    if not folders:
        fail(f"Archi rules not found at {pattern} — run ./bootstrap.sh")
    if len(folders) > 1:
        fail("More than one Archi model plugin found, cannot pick the rules:\n  " + "\n  ".join(folders))
    folder = Path(folders[0])
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


def check(model, rules, known_types):
    """Every problem of the model's relationships, one message each."""
    problems = []
    for rel in model.relationships:
        rid, rtype, src, dst = (rel[k] for k in ("ID", "Type", "Source", "Target"))
        # The exchange format writes types without the "Relationship" suffix of Archi's rules.
        full = f"{rtype}Relationship"
        missing = [(end, rel[end]) for end in ("Source", "Target") if rel[end] not in model.elements]
        for end, ident in missing:
            problems.append(f"{rid}: {end} '{ident}' is not an element ID")
        if full not in known_types:
            problems.append(f"{rid}: unknown relationship type '{rtype}'")
        if missing or full not in known_types:
            continue
        allowed = rules.get((model.elements[src], model.elements[dst]), set())
        if full not in allowed:
            names = ", ".join(sorted(a.removesuffix("Relationship") for a in allowed)) or "none"
            problems.append(
                f"{rid}: {rtype} is not allowed from {model.elements[src]} ('{src}') to "
                f"{model.elements[dst]} ('{dst}'); allowed: {names}"
            )
    return problems


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    model_file, archi_home = Path(argv[0]), argv[1]
    try:
        model = exchange.read(model_file.read_bytes())
    except (OSError, exchange.FormatError) as err:
        fail(f"{model_file}: {err}")
    rules, known_types = load_rules(archi_home)
    problems = check(model, rules, known_types)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    count = len(model.relationships)
    if problems:
        fail(f"relationships: {len(problems)} problem(s) in {count} checked")
    print(f"relationships: {count} checked, all allowed by ArchiMate 3.2")


if __name__ == "__main__":
    main(sys.argv[1:])
