#!/usr/bin/env python3
"""Validate ArchiMate exchange files against the official Open Group 3.1 schema (ADR 0009).

  python3 -I xsd_check.py FILE ...

The XSDs are read from the pinned Archi install (plugins/org.opengroup.archimate.xmlexchange_*.jar,
directory xsd/), extracted to a temporary directory, and checked against the sha256 values pinned
in tools/archi.env; there is no copy in the repo. An XML catalog maps the schema's import of
http://www.w3.org/2001/xml.xsd to the copy in the same jar, so xmllint runs with --nonet.

Exit codes: 0 valid, 1 a file is invalid (xmllint says where), 2 the check cannot run (xmllint or
Archi missing, schema files differ from the pins). Never passes when it could not check.
"""

from __future__ import annotations

import glob
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / "tools" / "archi.env"
# Schema file in the jar's xsd/ directory -> its pin in tools/archi.env.
PINS = {
    "archimate3_Diagram.xsd": "ARCHI_XSD_SHA256_DIAGRAM",
    "archimate3_View.xsd": "ARCHI_XSD_SHA256_VIEW",
    "archimate3_Model.xsd": "ARCHI_XSD_SHA256_MODEL",
    "xml.xsd": "ARCHI_XSD_SHA256_XML",
}
CATALOG = """<?xml version="1.0"?>
<catalog xmlns="urn:oasis:names:tc:entity:xmlns:xml:catalog">
  <system systemId="http://www.w3.org/2001/xml.xsd" uri="{uri}"/>
</catalog>
"""


class CheckError(Exception):
    """The validation could not run; the message says what to do."""


def read_env(path: Path) -> dict[str, str]:
    """KEY=VALUE lines of a shell file that bash also sources."""
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            env[key.strip()] = value.strip()
    return env


def extract_schemas(archi_home: Path, pins: dict[str, str], dest: Path) -> Path:
    """Extract xsd/ from Archi's exchange plugin into dest, check the pins, return the folder."""
    pattern = str(archi_home / "plugins" / "org.opengroup.archimate.xmlexchange_*.jar")
    jars = sorted(glob.glob(pattern))
    if not jars:
        raise CheckError(f"ArchiMate schema not found: no {pattern} — run ./bootstrap.sh")
    if len(jars) > 1:
        raise CheckError("More than one Archi exchange plugin found, cannot pick the schema:\n  "
                         + "\n  ".join(jars))
    with zipfile.ZipFile(jars[0]) as jar:
        for name, var in PINS.items():
            try:
                data = jar.read(f"xsd/{name}")
            except KeyError:
                raise CheckError(f"{jars[0]} has no xsd/{name}") from None
            digest = hashlib.sha256(data).hexdigest()
            if digest != pins.get(var):
                raise CheckError(
                    f"xsd/{name} in {jars[0]} has sha256 {digest}, but tools/archi.env pins "
                    f"{var}={pins.get(var, '(missing)')}. Upgrade Archi and the pins together, "
                    "deliberately, in one PR.")
            (dest / name).write_bytes(data)
    return dest


def validate(files: list[str], archi_home: Path, pins: dict[str, str]) -> int:
    xmllint = shutil.which("xmllint")
    with tempfile.TemporaryDirectory(prefix="archimate-xsd-") as tmp:
        xsd = extract_schemas(archi_home, pins, Path(tmp))
        if xmllint is None:
            raise CheckError("xmllint not found — run ./bootstrap.sh (it installs libxml2-utils "
                             "on Ubuntu, libxml2 on Arch)")
        catalog = xsd / "catalog.xml"
        catalog.write_text(CATALOG.format(uri=(xsd / "xml.xsd").as_uri()), encoding="utf-8")
        env = {**os.environ, "XML_CATALOG_FILES": str(catalog)}
        result = subprocess.run(
            [xmllint, "--noout", "--nonet", "--schema", str(xsd / "archimate3_Diagram.xsd"), *files],
            env=env, check=False, capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    if output:
        print(output, file=sys.stderr if result.returncode else sys.stdout)
    if result.returncode:
        print(f"schema: {len(files)} file(s) checked, not valid against the ArchiMate 3.1 "
              "exchange schema", file=sys.stderr)
        return 1
    print(f"schema: {len(files)} file(s) valid against the ArchiMate 3.1 exchange schema")
    return 0


def main(argv: list[str]) -> int:
    if not argv or any(a.startswith("-") for a in argv):
        print(__doc__, file=sys.stderr)
        return 2
    pins = read_env(ENV_FILE)
    home = os.environ.get("ARCHI_HOME") or str(
        Path.home() / ".local" / "opt" / f"archi-{pins.get('ARCHI_VERSION', '')}")
    try:
        return validate(argv, Path(home), pins)
    except CheckError as err:
        print(f"schema: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
