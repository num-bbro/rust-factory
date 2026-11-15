#!/usr/bin/env python3
"""Build an ArchiMate Open Exchange XML file from the factory's text model.

Source (docs/architecture/model/), all UTF-8 CSV in Archi's own CSV format, so a model
can also round-trip through Archi's File > Import/Export > CSV:

  elements.csv    "ID","Type","Name","Documentation","Specialization"
                  (one optional row of Type "ArchimateModel" names the model)
  relations.csv   "ID","Type","Name","Documentation","Source","Target","Specialization"
  properties.csv  "ID","Key","Value"            (optional)
  views.csv       "ID","Name","Viewpoint","Elements","Documentation"
                  Elements = space-separated element IDs. Factory extension, not Archi CSV.

Diagrams are generated: elements are placed in horizontal bands per ArchiMate layer
(motivation at the top, implementation at the bottom); a relationship is drawn whenever
both of its ends are on the view.

Usage: build_exchange.py <model-dir> <output.xml>
Exits non-zero with a list of problems if the model is inconsistent.
Standard library only, so it runs anywhere python3 exists.
"""

from __future__ import annotations

import csv
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "http://www.opengroup.org/xsd/archimate/3.0/"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
LANG = "en"

# ArchiMate 3.2 element types, grouped into the layer bands used for layout (top to bottom).
LAYERS: list[tuple[str, list[str]]] = [
    ("Motivation", ["Stakeholder", "Driver", "Assessment", "Goal", "Outcome", "Principle",
                    "Requirement", "Constraint", "Meaning", "Value"]),
    ("Strategy", ["Resource", "Capability", "ValueStream", "CourseOfAction"]),
    ("Business", ["BusinessActor", "BusinessRole", "BusinessCollaboration", "BusinessInterface",
                  "BusinessProcess", "BusinessFunction", "BusinessInteraction", "BusinessEvent",
                  "BusinessService", "BusinessObject", "Contract", "Representation", "Product"]),
    ("Application", ["ApplicationComponent", "ApplicationCollaboration", "ApplicationInterface",
                     "ApplicationFunction", "ApplicationInteraction", "ApplicationProcess",
                     "ApplicationEvent", "ApplicationService", "DataObject"]),
    ("Technology", ["Node", "Device", "SystemSoftware", "TechnologyCollaboration",
                    "TechnologyInterface", "Path", "CommunicationNetwork", "TechnologyFunction",
                    "TechnologyProcess", "TechnologyInteraction", "TechnologyEvent",
                    "TechnologyService", "Artifact", "Equipment", "Facility",
                    "DistributionNetwork", "Material"]),
    ("Implementation & Migration", ["WorkPackage", "Deliverable", "ImplementationEvent",
                                    "Plateau", "Gap"]),
    ("Other", ["Location", "Grouping"]),
]
LAYER_OF = {t: layer for layer, types in LAYERS for t in types}
RELATION_TYPES = {"Composition", "Aggregation", "Assignment", "Realization", "Serving", "Access",
                  "Influence", "Triggering", "Flow", "Specialization", "Association"}
VIEWPOINTS = {"", "Layered", "Motivation", "Strategy", "Organization", "Business Process Cooperation",
              "Product", "Application Cooperation", "Application Usage", "Technology",
              "Technology Usage", "Physical", "Implementation and Deployment",
              "Information Structure", "Service Realization", "Goal Realization",
              "Requirements Realization", "Stakeholder", "Capability Map", "Value Stream",
              "Project", "Migration", "Implementation and Migration"}

# Layout (pixels)
NODE_W, NODE_H, GAP_X, GAP_Y = 170, 60, 30, 25
BAND_PAD, BAND_LABEL, BAND_GAP, PER_ROW, MARGIN = 20, 25, 20, 5, 20


def read_csv(path: Path, required: bool = True) -> list[dict[str, str]]:
    if not path.exists():
        if required:
            raise SystemExit(f"error: missing {path}")
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:  # -sig: tolerate Excel's BOM
        return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def text_el(parent: ET.Element, tag: str, text: str) -> None:
    if text:
        el = ET.SubElement(parent, tag)
        el.set(XML_LANG, LANG)
        el.text = text


def main(model_dir: Path, out: Path) -> int:
    elements = read_csv(model_dir / "elements.csv")
    relations = read_csv(model_dir / "relations.csv")
    properties = read_csv(model_dir / "properties.csv", required=False)
    views = read_csv(model_dir / "views.csv", required=False)
    problems: list[str] = []

    model_row = next((e for e in elements if e["Type"] == "ArchimateModel"), None)
    elements = [e for e in elements if e["Type"] != "ArchimateModel"]

    # --- validate ------------------------------------------------------------------
    seen: set[str] = set()
    for row in [*elements, *relations]:
        if not row["ID"]:
            problems.append(f"row without ID: {row}")
        elif row["ID"] in seen:
            problems.append(f"duplicate ID {row['ID']}")
        seen.add(row["ID"])
    el_by_id = {e["ID"]: e for e in elements}
    for e in elements:
        if e["Type"] not in LAYER_OF:
            problems.append(f"{e['ID']}: unknown element type '{e['Type']}'")
        if not e["Name"]:
            problems.append(f"{e['ID']}: element has no Name")
    for r in relations:
        rtype = r["Type"].removesuffix("Relationship")
        if rtype not in RELATION_TYPES:
            problems.append(f"{r['ID']}: unknown relationship type '{r['Type']}'")
        for end in ("Source", "Target"):
            if r[end] not in el_by_id:
                problems.append(f"{r['ID']}: {end} '{r[end]}' is not an element ID")
    props_by_id: dict[str, list[tuple[str, str]]] = {}
    for p in properties:
        if p["ID"] not in seen and not (model_row and p["ID"] == model_row["ID"]):
            problems.append(f"properties.csv: unknown ID '{p['ID']}'")
        props_by_id.setdefault(p["ID"], []).append((p["Key"], p["Value"]))
    for v in views:
        if v["Viewpoint"] not in VIEWPOINTS:
            problems.append(f"{v['ID']}: unknown viewpoint '{v['Viewpoint']}'")
        for ref in v["Elements"].split():
            if ref not in el_by_id:
                problems.append(f"{v['ID']}: element '{ref}' does not exist")
        if v["ID"] in seen:
            problems.append(f"duplicate ID {v['ID']}")
        seen.add(v["ID"])
    if problems:
        print("Model problems:", *[f"  - {p}" for p in problems], sep="\n", file=sys.stderr)
        return 1

    # --- property definitions (Exchange format needs them declared once) -------------------
    keys = sorted({k for plist in props_by_id.values() for k, _ in plist})
    prop_def = {k: f"propid-{i + 1}" for i, k in enumerate(keys)}

    def add_props(parent: ET.Element, ident: str) -> None:
        plist = props_by_id.get(ident)
        if not plist:
            return
        holder = ET.SubElement(parent, "properties")
        for k, val in plist:
            p = ET.SubElement(holder, "property", propertyDefinitionRef=prop_def[k])
            text_el(p, "value", val)

    # --- model ----------------------------------------------------------------------
    ET.register_namespace("", NS)
    ET.register_namespace("xsi", XSI)
    root = ET.Element(f"{{{NS}}}model", identifier=(model_row or {}).get("ID") or "id-model")
    text_el(root, "name", (model_row or {}).get("Name") or model_dir.name)
    text_el(root, "documentation", (model_row or {}).get("Documentation", ""))
    if model_row:
        add_props(root, model_row["ID"])

    xel = ET.SubElement(root, "elements")
    for e in elements:
        node = ET.SubElement(xel, "element", identifier=e["ID"])
        node.set(f"{{{XSI}}}type", e["Type"])
        text_el(node, "name", e["Name"])
        text_el(node, "documentation", e.get("Documentation", ""))
        add_props(node, e["ID"])

    if relations:
        xrel = ET.SubElement(root, "relationships")
        for r in relations:
            node = ET.SubElement(xrel, "relationship", identifier=r["ID"],
                                 source=r["Source"], target=r["Target"])
            node.set(f"{{{XSI}}}type", r["Type"].removesuffix("Relationship"))
            text_el(node, "name", r.get("Name", ""))
            text_el(node, "documentation", r.get("Documentation", ""))
            add_props(node, r["ID"])

    if keys:
        xdefs = ET.SubElement(root, "propertyDefinitions")
        for k in keys:
            d = ET.SubElement(xdefs, "propertyDefinition", identifier=prop_def[k], type="string")
            text_el(d, "name", k)

    if views:
        diagrams = ET.SubElement(ET.SubElement(root, "views"), "diagrams")
        for v in views:
            add_view(diagrams, v, el_by_id, relations)

    out.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root)
    ET.ElementTree(root).write(out, encoding="UTF-8", xml_declaration=True)
    print(f"{out}: {len(elements)} elements, {len(relations)} relationships, {len(views)} views")
    return 0


def add_view(diagrams: ET.Element, v: dict[str, str], el_by_id: dict[str, dict[str, str]],
             relations: list[dict[str, str]]) -> None:
    view = ET.SubElement(diagrams, "view", identifier=v["ID"])
    view.set(f"{{{XSI}}}type", "Diagram")
    if v["Viewpoint"]:
        view.set("viewpoint", v["Viewpoint"])
    text_el(view, "name", v["Name"])
    text_el(view, "documentation", v.get("Documentation", ""))

    refs = v["Elements"].split()
    node_of: dict[str, str] = {}
    y = MARGIN
    band_w = MARGIN + PER_ROW * (NODE_W + GAP_X) - GAP_X + 2 * BAND_PAD
    for layer, _ in LAYERS:
        members = [r for r in refs if LAYER_OF[el_by_id[r]["Type"]] == layer]
        if not members:
            continue
        rows = (len(members) + PER_ROW - 1) // PER_ROW
        band_h = BAND_LABEL + rows * (NODE_H + GAP_Y) - GAP_Y + 2 * BAND_PAD
        band = ET.SubElement(view, "node", identifier=f"{v['ID']}-band-{len(node_of)}",
                             x=str(MARGIN), y=str(y), w=str(band_w), h=str(band_h))
        band.set(f"{{{XSI}}}type", "Container")
        text_el(band, "label", layer)
        for i, ref in enumerate(members):
            nid = f"{v['ID']}-n-{ref}"
            node_of[ref] = nid
            # Exchange-format coordinates are absolute, even for nested nodes.
            nx = MARGIN + BAND_PAD + (i % PER_ROW) * (NODE_W + GAP_X)
            ny = y + BAND_LABEL + BAND_PAD + (i // PER_ROW) * (NODE_H + GAP_Y)
            n = ET.SubElement(band, "node", identifier=nid, elementRef=ref,
                              x=str(nx), y=str(ny), w=str(NODE_W), h=str(NODE_H))
            n.set(f"{{{XSI}}}type", "Element")
        y += band_h + BAND_GAP

    for r in relations:
        if r["Source"] in node_of and r["Target"] in node_of:
            c = ET.SubElement(view, "connection", identifier=f"{v['ID']}-c-{r['ID']}",
                              relationshipRef=r["ID"], source=node_of[r["Source"]],
                              target=node_of[r["Target"]])
            c.set(f"{{{XSI}}}type", "Relationship")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
