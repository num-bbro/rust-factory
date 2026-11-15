"""The canonical form of an ArchiMate exchange file (ADR 0009), and the view emission it shares
with build_exchange.py.

`canonical(data)` reads an Open Group ArchiMate Model Exchange file and returns it in the one
canonical form of ADR 0009:

* UTF-8, LF, 2-space indent, one fixed attribute order (ATTR_ORDER), sections and children in
  schema order, elements, relationships, property definitions and views sorted by identifier
  (properties keep their order: a repeated property is an ordered list);
* `xml:lang="en"` on every name, label, documentation and value; at most one of each per owner;
* an empty `documentation` is omitted and its text never ends in a newline; empty `properties`
  are omitted;
* text is escaped, never CDATA; comments, processing instructions and DOCTYPEs are rejected (they
  would not survive a parse-and-serialise round);
* `xsi:schemaLocation` is always written;
* property definitions are named `propid-<slug of their name>`; unused ones are dropped (and
  reported as a note);
* an `Access` relationship always states `accessType` (a missing one becomes the schema default,
  `Access`; Archi would read it as `Write`);
* every view is laid out again from its member elements (bands, nesting, coordinates, node and
  connection identifiers, connections) by layout.py, unless it has the property
  `Layout = manual`: such a view is copied as it is, only property-definition references are
  renamed.

Anything else the standard allows but this form does not know (metadata, organizations,
viewpoints, foreign-namespace extensions, unknown attributes, hand-made nodes in an automatic
view) is rejected with a message naming where it is: content is never dropped silently.

Pure functions, standard library only.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Sibling module. Added explicitly because `python3 -I` (isolated mode) leaves the script's
# own folder off sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import layout  # noqa: E402

NS = "http://www.opengroup.org/xsd/archimate/3.0/"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
XML = "http://www.w3.org/XML/1998/namespace"
XML_LANG = f"{{{XML}}}lang"
XSI_TYPE = f"{{{XSI}}}type"
XSI_LOCATION = f"{{{XSI}}}schemaLocation"
LANG = "en"
SCHEMA_LOCATION = f"{NS} http://www.opengroup.org/xsd/archimate/3.1/archimate3_Diagram.xsd"
MANUAL_LAYOUT = ("Layout", "manual")       # view property that keeps a hand-arranged view

# Attributes are written in this order; any other (only possible in a manual view) follows,
# sorted by name.
ATTR_ORDER = [XSI_LOCATION, "identifier", XSI_TYPE, "elementRef", "relationshipRef", "source",
              "target", "accessType", "modifier", "isDirected", "propertyDefinitionRef", "type",
              "viewpoint", "version", "x", "y", "w", "h", "r", "g", "b", "a", XML_LANG]
_ATTR_RANK = {name: i for i, name in enumerate(ATTR_ORDER)}
_TEXT_ESCAPES = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;", "\r": "&#13;"})
_ATTR_ESCAPES = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
                               "\n": "&#10;", "\r": "&#13;", "\t": "&#9;"})
_PREFIX = {"": "", XSI: "xsi:", XML: "xml:"}


class FormatError(Exception):
    """The input cannot be put in canonical form; `problems` says where and why."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


# --- view emission, shared with build_exchange.py -----------------------------------------------

def text_el(parent: ET.Element, tag: str, text: str) -> None:
    """Add <tag xml:lang="en">text</tag>, or nothing when the text is empty."""
    if text:
        el = ET.SubElement(parent, tag)
        el.set(XML_LANG, LANG)
        el.text = text


def add_diagram(view: ET.Element, view_id: str, refs: list[str], types: dict[str, str],
                rels: list[dict[str, str]]) -> None:
    """Append the laid-out nodes and connections of one view to `view`.

    `refs` are the member element ids, `types` maps each to its element type, `rels` are the
    model's relationships as {"ID", "Type", "Source", "Target"}; a relationship is drawn when both
    of its ends are members. Node and connection identifiers derive from the view and element or
    relationship ids, so the same input always gives the same output.
    """
    lay = layout.layout(refs, types, rels)
    node_id = {ref: f"{view_id}-n-{ref}" for ref in refs}

    def xywh(x: float, y: float, w: float, h: float) -> dict[str, str]:
        return {"x": str(round(x)), "y": str(round(y)), "w": str(round(w)), "h": str(round(h))}

    def add_box(parent_el: ET.Element, b: layout.Box) -> None:
        n = ET.SubElement(parent_el, "node", identifier=node_id[b.ref], elementRef=b.ref,
                          **xywh(b.x, b.y, b.w, b.h))
        n.set(XSI_TYPE, "Element")
        for c in b.children:                   # nested = composition/aggregation shown visually
            add_box(n, c)

    for i, band in enumerate(lay.bands):
        g = ET.SubElement(view, "node", identifier=f"{view_id}-band-{i}",
                          **xywh(band.x, band.y, band.w, band.h))
        g.set(XSI_TYPE, "Container")
        text_el(g, "label", band.label)
        for row in band.rows:
            for b in row.items:
                add_box(g, b)

    for line in lay.lines:
        c = ET.SubElement(view, "connection", identifier=f"{view_id}-c-{line.rel_id}",
                          relationshipRef=line.rel_id, source=node_id[line.source],
                          target=node_id[line.target])
        c.set(XSI_TYPE, "Relationship")
        for bx, by in line.bends:
            ET.SubElement(c, "bendpoint", x=str(round(bx)), y=str(round(by)))


# --- writing ------------------------------------------------------------------------------------

def _split(tag: str) -> tuple[str, str]:
    if tag.startswith("{"):
        ns, _, local = tag[1:].partition("}")
        return ns, local
    return "", tag


def _attr_key(item: tuple[str, str]) -> tuple[int, str]:
    return _ATTR_RANK.get(item[0], len(ATTR_ORDER)), item[0]


def serialize(root: ET.Element) -> str:
    """Write a tree in canonical layout. Tags are written without prefix (default namespace)."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']

    def write(el: ET.Element, depth: int, decl: str = "") -> None:
        pad = "  " * depth
        tag = _split(el.tag)[1]
        attrs = decl + "".join(
            f' {_PREFIX[_split(k)[0]]}{_split(k)[1]}="{v.translate(_ATTR_ESCAPES)}"'
            for k, v in sorted(el.attrib.items(), key=_attr_key))
        if len(el):
            lines.append(f"{pad}<{tag}{attrs}>")
            for child in el:
                write(child, depth + 1)
            lines.append(f"{pad}</{tag}>")
        elif el.text:
            lines.append(f"{pad}<{tag}{attrs}>{el.text.translate(_TEXT_ESCAPES)}</{tag}>")
        else:
            lines.append(f"{pad}<{tag}{attrs}/>")

    write(root, 0, f' xmlns="{NS}" xmlns:xsi="{XSI}"')
    return "\n".join(lines) + "\n"


# --- reading ------------------------------------------------------------------------------------

def canonical(data: bytes) -> tuple[str, list[str]]:
    """Return (the file in canonical form, notes about what was normalised away).

    Raises FormatError listing every problem found.
    """
    problems = []
    try:
        events = ET.XMLPullParser(events=("comment", "pi"))
        events.feed(data)
        events.close()
        root = ET.fromstring(data)
    except ET.ParseError as err:
        raise FormatError([f"not well-formed XML: {err}"]) from None
    for kind, item in events.read_events():
        what = "an XML comment" if kind == "comment" else "a processing instruction"
        text = " ".join((item.text or "").split())[:40]
        problems.append(f"{what} ('{text}') is not allowed: it would not survive formatting; "
                        "put the text in a documentation element")
    if b"<!DOCTYPE" in data:
        problems.append("a DOCTYPE is not allowed in an exchange file")
    c = _Canonicaliser(problems)
    out = c.model(root)
    if problems or out is None:
        raise FormatError(problems)
    return serialize(out), c.notes


def _ident(el: ET.Element) -> str:
    return el.get("identifier", "")


class _Canonicaliser:
    def __init__(self, problems: list[str]):
        self.problems = problems
        self.notes: list[str] = []
        self.prop_ids: dict[str, str] = {}               # input definition id -> propid-<slug>
        self.prop_defs: dict[str, tuple[str, str, str, str]] = {}  # new id -> name, type, doc, old id
        self.used: set[str] = set()
        self.types: dict[str, str] = {}                  # element id -> element type
        self.rels: list[dict[str, str]] = []

    def problem(self, where: str, message: str) -> None:
        self.problems.append(f"{where}: {message}")

    # -- generic helpers --

    def children(self, el: ET.Element, where: str, allowed: tuple[str, ...]) -> dict[str, list[ET.Element]]:
        """Children grouped by tag; anything else, and stray text, is a problem."""
        found: dict[str, list[ET.Element]] = {tag: [] for tag in allowed}
        if (el.text or "").strip():
            self.problem(where, f"unexpected text inside <{_split(el.tag)[1]}>")
        for child in el:
            ns, tag = _split(child.tag)
            if ns != NS or tag not in found:
                name = f"{{{ns}}}{tag}" if ns != NS else tag
                self.problem(where, f"<{name}> is not supported here by the canonical form (ADR 0009)")
                continue
            if (child.tail or "").strip():
                self.problem(where, f"unexpected text after <{tag}>")
            found[tag].append(child)
        return found

    def single(self, found: dict[str, list[ET.Element]], tag: str, where: str) -> ET.Element | None:
        if len(found[tag]) > 1:
            self.problem(where, f"more than one <{tag}>")
        return found[tag][0] if found[tag] else None

    def attrs(self, el: ET.Element, where: str, allowed: set[str]) -> dict[str, str]:
        for key in el.attrib:
            if key not in allowed:
                ns, name = _split(key)
                self.problem(where, f"attribute {_PREFIX.get(ns, '{' + ns + '}')}{name} is not "
                                    f"supported on <{_split(el.tag)[1]}>")
        return dict(el.attrib)

    def text(self, els: list[ET.Element], where: str, tag: str) -> str | None:
        """The one English text of a name / label / documentation / value list, or None."""
        result = None
        for el in els:
            self.attrs(el, where, {XML_LANG})
            if len(el):
                self.problem(where, f"<{tag}> must hold text only")
            lang = el.get(XML_LANG, LANG)
            if lang != LANG:
                self.problem(where, f'<{tag} xml:lang="{lang}">: the model is written with '
                                    'xml:lang="en" only (Thai text needs no language tag)')
            elif result is not None:
                self.problem(where, f"more than one <{tag}> (Archi keeps only the first)")
            else:
                result = el.text or ""
        return result

    def lang_el(self, parent: ET.Element, tag: str, text: str) -> None:
        el = ET.SubElement(parent, tag)
        el.set(XML_LANG, LANG)
        el.text = text

    def named(self, out: ET.Element, found: dict[str, list[ET.Element]], where: str,
              required: bool) -> None:
        """name, documentation, properties: in that order, as the schema requires."""
        name = self.text(found["name"], where, "name")
        if name is None:
            if required:
                self.problem(where, "has no <name>")
        else:
            self.lang_el(out, "name", name)
        doc = (self.text(found["documentation"], where, "documentation") or "").rstrip("\n")
        if doc:
            self.lang_el(out, "documentation", doc)
        if "properties" in found:
            self.properties(out, self.single(found, "properties", where), where)

    def properties(self, out: ET.Element, holder: ET.Element | None, where: str) -> None:
        if holder is None:
            return
        self.attrs(holder, where, set())
        props = self.children(holder, where, ("property",))["property"]
        if not props:
            return                                       # the schema rejects an empty <properties/>
        out_holder = ET.SubElement(out, "properties")
        for p in props:
            ref = self.attrs(p, where, {"propertyDefinitionRef"}).get("propertyDefinitionRef", "")
            new = self.prop_ids.get(ref)
            if new is None:
                self.problem(where, f"property refers to unknown property definition '{ref}'")
                continue
            self.used.add(new)
            q = ET.SubElement(out_holder, "property", propertyDefinitionRef=new)
            value = self.text(self.children(p, where, ("value",))["value"], where, "value")
            if value is None:
                self.problem(where, f"property '{self.prop_defs[new][0]}' has no <value>")
            else:
                self.lang_el(q, "value", value)

    # -- model --

    def model(self, root: ET.Element) -> ET.Element | None:
        if _split(root.tag) != (NS, "model"):
            self.problem("root", f"expected <model> in namespace {NS}, found <{root.tag}>")
            return None
        a = self.attrs(root, "model", {"identifier", "version", XSI_LOCATION})
        found = self.children(root, "model", (
            "name", "documentation", "properties", "metadata", "elements", "relationships",
            "organizations", "propertyDefinitions", "views"))
        for tag in ("metadata", "organizations"):
            if found[tag]:
                self.problem("model", f"<{tag}> is not supported by the canonical form (ADR 0009); "
                                      "remove it")
        if not a.get("identifier"):
            self.problem("model", "has no identifier")
        # Definitions first: every property reference is renamed through them.
        self.read_prop_defs(self.single(found, "propertyDefinitions", "model"))

        out = ET.Element("model")
        out.set(XSI_LOCATION, SCHEMA_LOCATION)
        out.set("identifier", a.get("identifier", ""))
        if "version" in a:
            out.set("version", a["version"])
        self.named(out, found, "model", required=True)

        elements = self.single(found, "elements", "model")
        relationships = self.single(found, "relationships", "model")
        views = self.single(found, "views", "model")
        out_elements = self.elements(elements) if elements is not None else None
        out_rels = self.relationships(relationships) if relationships is not None else None
        out_views = self.views(views) if views is not None else None
        for section in (out_elements, out_rels, self.write_prop_defs(), out_views):
            if section is not None and len(section):
                out.append(section)
        return out

    def elements(self, holder: ET.Element) -> ET.Element:
        self.attrs(holder, "elements", set())
        out = ET.Element("elements")
        for e in sorted(self.children(holder, "elements", ("element",))["element"], key=_ident):
            where = f"element '{_ident(e)}'"
            a = self.attrs(e, where, {"identifier", XSI_TYPE})
            if not a.get("identifier") or not a.get(XSI_TYPE):
                self.problem(where, "needs both identifier and xsi:type")
            self.types[a.get("identifier", "")] = a.get(XSI_TYPE, "")
            o = ET.SubElement(out, "element", identifier=a.get("identifier", ""))
            o.set(XSI_TYPE, a.get(XSI_TYPE, ""))
            self.named(o, self.children(e, where, ("name", "documentation", "properties")), where,
                       required=True)
        return out

    def relationships(self, holder: ET.Element) -> ET.Element:
        self.attrs(holder, "relationships", set())
        out = ET.Element("relationships")
        found = self.children(holder, "relationships", ("relationship",))["relationship"]
        for r in sorted(found, key=_ident):
            where = f"relationship '{_ident(r)}'"
            a = self.attrs(r, where, {"identifier", XSI_TYPE, "source", "target", "accessType",
                                      "modifier", "isDirected"})
            for key in ("identifier", XSI_TYPE, "source", "target"):
                if not a.get(key):
                    self.problem(where, f"has no {_PREFIX[_split(key)[0]]}{_split(key)[1]}")
            if a.get(XSI_TYPE) == "Access":
                a.setdefault("accessType", "Access")     # the schema's default, stated explicitly
            o = ET.SubElement(out, "relationship", a)
            self.named(o, self.children(r, where, ("name", "documentation", "properties")), where,
                       required=False)
            self.rels.append({"ID": a.get("identifier", ""), "Type": a.get(XSI_TYPE, ""),
                              "Source": a.get("source", ""), "Target": a.get("target", "")})
        return out

    # -- property definitions --

    def read_prop_defs(self, holder: ET.Element | None) -> None:
        if holder is None:
            return
        self.attrs(holder, "propertyDefinitions", set())
        found = self.children(holder, "propertyDefinitions", ("propertyDefinition",))
        for d in found["propertyDefinition"]:
            old = _ident(d)
            where = f"property definition '{old}'"
            a = self.attrs(d, where, {"identifier", "type"})
            f = self.children(d, where, ("name", "documentation"))
            name = self.text(f["name"], where, "name")
            doc = (self.text(f["documentation"], where, "documentation") or "").rstrip("\n")
            if not name:
                self.problem(where, "has no <name>")
                continue
            if not a.get("type"):
                self.problem(where, "has no type (e.g. type=\"string\")")
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            if not slug:
                self.problem(where, f"name '{name}' gives no identifier: it needs a letter a-z or "
                                    "a digit")
                continue
            new = f"propid-{slug}"
            if new in self.prop_defs:
                self.problem(where, f"names '{name}' and '{self.prop_defs[new][0]}' both give "
                                    f"the identifier {new}; rename one")
                continue
            if old in self.prop_ids:
                self.problem(where, "duplicate identifier")
            self.prop_ids[old] = new
            self.prop_defs[new] = (name, a.get("type", ""), doc, old)

    def write_prop_defs(self) -> ET.Element:
        out = ET.Element("propertyDefinitions")
        for new in sorted(self.prop_defs):
            name, dtype, doc, old = self.prop_defs[new]
            if new not in self.used:
                self.notes.append(f"dropped unused property definition '{name}' ({old})")
                continue
            d = ET.SubElement(out, "propertyDefinition", identifier=new, type=dtype)
            self.lang_el(d, "name", name)
            if doc:
                self.lang_el(d, "documentation", doc)
        return out

    # -- views --

    def views(self, holder: ET.Element) -> ET.Element:
        self.attrs(holder, "views", set())
        out = ET.Element("views")
        found = self.children(holder, "views", ("viewpoints", "diagrams"))
        if found["viewpoints"]:
            self.problem("views", "<viewpoints> is not supported by the canonical form (ADR 0009)")
        diagrams = self.single(found, "diagrams", "views")
        if diagrams is None:
            return out
        self.attrs(diagrams, "diagrams", set())
        listed = self.children(diagrams, "diagrams", ("view",))["view"]
        if listed:
            out_diagrams = ET.SubElement(out, "diagrams")
            for v in sorted(listed, key=_ident):
                if self.is_manual(v):
                    out_diagrams.append(self.verbatim(v, f"view '{_ident(v)}'"))
                else:
                    self.auto_view(out_diagrams, v)
        return out

    def is_manual(self, v: ET.Element) -> bool:
        for p in v.iterfind(f"{{{NS}}}properties/{{{NS}}}property"):
            new = self.prop_ids.get(p.get("propertyDefinitionRef", ""))
            values = [(x.text or "") for x in p.iterfind(f"{{{NS}}}value")]
            if new and (self.prop_defs[new][0], values) == (MANUAL_LAYOUT[0], [MANUAL_LAYOUT[1]]):
                return True
        return False

    def verbatim(self, el: ET.Element, where: str) -> ET.Element:
        """Copy a hand-arranged view as it is; only property-definition references are renamed."""
        ns, tag = _split(el.tag)
        if ns != NS:
            self.problem(where, f"<{el.tag}> is not in the ArchiMate namespace")
        out = ET.Element(tag)
        for key, value in el.attrib.items():
            if _split(key)[0] not in _PREFIX:
                self.problem(where, f"attribute {key} is in an unsupported namespace")
                continue
            if key == "propertyDefinitionRef":
                new = self.prop_ids.get(value)
                if new is None:
                    self.problem(where, f"property refers to unknown property definition '{value}'")
                else:
                    self.used.add(new)
                    value = new
            out.set(key, value)
        if len(el) and (el.text or "").strip():
            self.problem(where, f"<{tag}> mixes text and elements")
        elif not len(el):
            out.text = el.text
        for child in el:
            out.append(self.verbatim(child, where))
        return out

    def auto_view(self, out_diagrams: ET.Element, v: ET.Element) -> None:
        vid = _ident(v)
        where = f"view '{vid}'"
        problems_before = len(self.problems)
        a = self.attrs(v, where, {"identifier", XSI_TYPE, "viewpoint"})
        if a.get(XSI_TYPE) != "Diagram":
            self.problem(where, f'xsi:type must be "Diagram", found "{a.get(XSI_TYPE, "")}"')
        found = self.children(v, where, ("name", "documentation", "properties", "node", "connection"))
        out = ET.SubElement(out_diagrams, "view", identifier=vid)
        out.set(XSI_TYPE, "Diagram")
        if a.get("viewpoint"):
            out.set("viewpoint", a["viewpoint"])
        self.named(out, found, where, required=True)

        refs: list[str] = []
        for node in found["node"]:
            self.members(node, vid, where, refs)
        for c in found["connection"]:                    # generated again from the members
            if c.get(XSI_TYPE) != "Relationship":
                self.problem(where, f"connection '{_ident(c)}' of type {c.get(XSI_TYPE)} is not "
                                    "generated by the formatter; set the view property "
                                    "Layout = manual to keep a hand-arranged view")
            self.attrs(c, where, {"identifier", XSI_TYPE, "relationshipRef", "source", "target"})
            self.children(c, where, ("bendpoint",))
        members = sorted(set(refs))
        rel_ids = {r["ID"] for r in self.rels}
        for ref in members:
            if ref not in self.types:
                what = "a relationship" if ref in rel_ids else "not an element of the model"
                self.problem(where, f"node elementRef '{ref}' is {what}")
            elif self.types[ref] not in layout.ELEMENT_TYPES:
                self.problem(where, f"'{ref}' is a {self.types[ref]}, which the automatic layout "
                                    "cannot place; set the view property Layout = manual")
        if len(self.problems) > problems_before:
            return
        rels = sorted(self.rels, key=lambda r: r["ID"])
        add_diagram(out, vid, members, {r: self.types[r] for r in members}, rels)

    def members(self, node: ET.Element, vid: str, where: str, refs: list[str]) -> None:
        """Collect the element ids of a (bare or formatted) automatic view."""
        kind, ident = node.get(XSI_TYPE), _ident(node)
        box = {"identifier", XSI_TYPE, "x", "y", "w", "h"}
        if kind == "Element":
            self.attrs(node, where, box | {"elementRef"})
            if node.get("elementRef"):
                refs.append(node.get("elementRef", ""))
            else:
                self.problem(where, f"node '{ident}' has no elementRef")
            nested = self.children(node, where, ("node",))
        elif kind == "Container" and re.fullmatch(re.escape(vid) + r"-band-\d+", ident):
            self.attrs(node, where, box)             # a layer band the formatter generated
            nested = self.children(node, where, ("label", "node"))
        else:
            self.problem(where, f"node '{ident}' of type {kind} is not generated by the formatter: "
                                'an automatic view lists only <node xsi:type="Element" '
                                'elementRef="…"/>; set the view property Layout = manual to keep '
                                "a hand-arranged view")
            return
        for child in nested["node"]:
            self.members(child, vid, where, refs)
