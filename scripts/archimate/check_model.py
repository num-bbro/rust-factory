#!/usr/bin/env python3
"""Check the exchange model's own rules, beyond the schema and the relationship rules (ADR 0009).

  python3 -I check_model.py <model.xml> <docs-dir>

* identifiers follow the convention `id-<layer>-<kind>-<slug>`, `id-rel-NNN`, `id-view-<slug>`
  (the model itself: `id-model-<slug>`);
* every view member is an element, and every diagram connection joins nodes of its
  relationship's two ends (neither the schema nor Archi checks this);
* every `View` property names an existing view;
* every `id-…` written in backticks in a Markdown file under <docs-dir> exists in the model, so
  the narrative and the model cannot silently drift apart.

Prints every problem, then exits 1; prints one line per check and exits 0 when all pass.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Sibling module. Added explicitly because `python3 -I` (isolated mode) leaves the script's
# own folder off sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import exchange  # noqa: E402

SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
ELEMENT_ID = re.compile(rf"id-(?:mot|str|bus|app|tech|impl)-[a-z0-9]+-{SLUG}")
RELATIONSHIP_ID = re.compile(r"id-rel-\d{3,}")
VIEW_ID = re.compile(rf"id-view-{SLUG}")
MODEL_ID = re.compile(rf"id-model-{SLUG}")
DOC_REF = re.compile(r"`(id-[a-z0-9-]+)`")


def id_convention(model: exchange.Model) -> list[str]:
    groups = [("model", [model.identifier], MODEL_ID, "id-model-<slug>"),
              ("element", list(model.elements), ELEMENT_ID, "id-<layer>-<kind>-<slug>, layer one "
               "of mot, str, bus, app, tech, impl"),
              ("relationship", [r["ID"] for r in model.relationships], RELATIONSHIP_ID, "id-rel-NNN"),
              ("view", list(model.views), VIEW_ID, "id-view-<slug>")]
    return [f"{what} '{ident}' does not follow the ID convention {rule}"
            for what, idents, pattern, rule in groups
            for ident in idents if not pattern.fullmatch(ident)]


def views(model: exchange.Model) -> list[str]:
    problems = [f"view '{vid}': member '{ref}' is not an element of the model"
                for vid, refs in model.views.items() for ref in refs if ref not in model.elements]
    rels = {r["ID"]: r for r in model.relationships}
    for c in model.connections:
        rel = rels.get(c.relationship)
        if rel is None:
            problems.append(f"view '{c.view}': connection '{c.identifier}' refers to unknown "
                            f"relationship '{c.relationship}'")
        elif (c.source, c.target) != (rel["Source"], rel["Target"]):
            problems.append(f"view '{c.view}': connection '{c.identifier}' joins '{c.source}' → "
                            f"'{c.target}', but {c.relationship} joins '{rel['Source']}' → "
                            f"'{rel['Target']}'")
    problems += [f"'{owner}': property View = '{value}' names no view of the model"
                 for owner, name, value in model.properties
                 if name == "View" and value not in model.views]
    return problems


def doc_refs(model: exchange.Model, docs: Path) -> list[str]:
    known = model.identifiers()
    problems = []
    for page in sorted(docs.rglob("*.md")):
        for ref in sorted(set(DOC_REF.findall(page.read_text(encoding="utf-8")))):
            if ref not in known:
                problems.append(f"{page}: {ref} is mentioned but is not in the model")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    model_file, docs = Path(argv[0]), Path(argv[1])
    try:
        model = exchange.read(model_file.read_bytes())
    except (OSError, exchange.FormatError) as err:
        print(f"{model_file}: {err}", file=sys.stderr)
        return 1
    checks = [("IDs: all follow the convention", id_convention(model)),
              ("views: all members are elements, connections match their relationships, "
               "View properties name views", views(model)),
              ("docs: all element references resolve", doc_refs(model, docs))]
    failed = False
    for ok, problems in checks:
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        failed = failed or bool(problems)
        if not problems:
            print(ok)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
