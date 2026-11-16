"""Tests of the official-schema validation (xsd_check.py), ADR 0009.

The tests that run xmllint against the real ArchiMate schema need xmllint and the pinned Archi
install; without them they are skipped and say so. That cannot hide a missing tool in a gate:
`just check` also runs `just model-check`, which validates docs/architecture/model.xml with the
same script and fails ("run ./bootstrap.sh") when xmllint or Archi is missing. The pin and
missing-tool tests below use a fake Archi plugin and need neither.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import xsd_check  # noqa: E402

PINS = xsd_check.read_env(xsd_check.ENV_FILE)
ARCHI_HOME = Path(os.environ.get("ARCHI_HOME")
                  or Path.home() / ".local" / "opt" / f"archi-{PINS['ARCHI_VERSION']}")
HAVE_ARCHI = any((ARCHI_HOME / "plugins").glob("org.opengroup.archimate.xmlexchange_*.jar"))
HAVE_XMLLINT = shutil.which("xmllint") is not None
FIXTURES = HERE / "fixtures"


def quiet(func, *args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return func(*args)


@unittest.skipUnless(HAVE_ARCHI and HAVE_XMLLINT,
                     "needs xmllint and the pinned Archi (run ./bootstrap.sh); "
                     "just model-check fails without them")
class OfficialSchema(unittest.TestCase):
    def test_canonical_fixture_is_valid(self):
        self.assertEqual(quiet(xsd_check.validate, [str(FIXTURES / "canonical.xml")], ARCHI_HOME,
                               PINS), 0)

    def test_formatter_input_with_a_bare_view_is_invalid(self):
        # bare.xml breaks the schema in several ways (documentation before name, bare nodes, …).
        self.assertEqual(quiet(xsd_check.validate, [str(FIXTURES / "bare.xml")], ARCHI_HOME,
                               PINS), 1)


class Pins(unittest.TestCase):
    def fake_archi(self, root: Path, content: bytes) -> Path:
        plugins = root / "plugins"
        plugins.mkdir()
        with zipfile.ZipFile(plugins / "org.opengroup.archimate.xmlexchange_1.0.jar", "w") as jar:
            for name in xsd_check.PINS:
                jar.writestr(f"xsd/{name}", content)
        return root

    def test_schema_that_differs_from_the_pin_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self.fake_archi(Path(tmp), b"<not the official schema/>")
            with self.assertRaisesRegex(xsd_check.CheckError, r"tools/archi.env pins"):
                xsd_check.validate(["model.xml"], home, PINS)

    def test_missing_xmllint_fails_and_names_bootstrap(self):
        content = b"<schema/>"
        pins = {var: hashlib.sha256(content).hexdigest() for var in xsd_check.PINS.values()}
        with tempfile.TemporaryDirectory() as tmp:
            home = self.fake_archi(Path(tmp), content)
            with mock.patch.object(xsd_check.shutil, "which", return_value=None):
                with self.assertRaisesRegex(xsd_check.CheckError, r"xmllint not found .*bootstrap"):
                    xsd_check.validate(["model.xml"], home, pins)

    @unittest.skipUnless(HAVE_XMLLINT, "needs xmllint (run ./bootstrap.sh)")
    def test_schema_that_does_not_compile_is_a_setup_error_not_an_invalid_file(self):
        content = b"<not-a-schema/>"
        pins = {var: hashlib.sha256(content).hexdigest() for var in xsd_check.PINS.values()}
        with tempfile.TemporaryDirectory() as tmp:
            home = self.fake_archi(Path(tmp), content)
            with self.assertRaisesRegex(xsd_check.CheckError, r"xmllint could not check"):
                quiet(xsd_check.validate, [str(FIXTURES / "canonical.xml")], home, pins)

    def test_missing_archi_fails_and_names_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(xsd_check.CheckError, r"run ./bootstrap.sh"):
                xsd_check.validate(["model.xml"], Path(tmp), PINS)

    def test_all_four_schema_files_are_pinned(self):
        for var in xsd_check.PINS.values():
            self.assertRegex(PINS.get(var, ""), r"^[0-9a-f]{64}$", var)


if __name__ == "__main__":
    unittest.main()
