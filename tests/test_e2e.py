import os
import re
import unittest

from mdtrans import config
from mdtrans.assemble import assemble_file
from mdtrans.digest import digest_file
from mdtrans.repair import repair_file
from mdtrans.translate import build_system, translate_file
from tests.helpers import make_project

os.environ["MDTRANS_RETRY_SLEEP"] = "0"

DOC = """# Guide

Intro with `code`, a [link](https://ex.com) and 42 apples.

## Part

- one item
- two items, 3.5 kg

```sh
echo hi
```
"""
TOML = 'source_lang = "en"\ntargets = ["vi"]\nfiles = ["*.md"]\nout = "{lang}/{name}"\nunit_heading_level = 2\n'


def _source(user: str) -> str:
    m = re.search(r"<source>\n(.*)\n</source>", user, re.S)
    return m.group(1) if m else user


class Echo:
    """Identity 'translation'; repair returns the source."""

    calls = 0

    def complete(self, system, user):
        self.calls += 1
        return _source(user)


class DropOnce(Echo):
    def complete(self, system, user):
        self.calls += 1
        if "<source>" in user:
            return _source(user)
        return re.sub(r"⟦P\d+⟧", "", user)


class Broken(Echo):
    def complete(self, system, user):
        self.calls += 1
        return "garbage"


def pipeline(backend):
    cfg = make_project({"doc.md": DOC}, TOML)
    src = config.sources(cfg)[0]
    wd = digest_file(cfg, src, "vi")
    translate_file(wd, backend, cfg, "vi", {}, "")
    return wd, repair_file(wd, backend, cfg, "vi", {}, "")


class E2ETest(unittest.TestCase):
    def test_identity_round_trip(self):
        wd, rep = pipeline(Echo())
        self.assertEqual(rep.get("ok"), len(rep["units"]))
        self.assertEqual(assemble_file(wd), DOC)

    def test_repair_restores_dropped_placeholders(self):
        b = DropOnce()
        wd, rep = pipeline(b)
        self.assertEqual(rep.get("ok"), len(rep["units"]))
        self.assertEqual(assemble_file(wd), DOC)

    def test_unfixable_marked_needs_human(self):
        wd, rep = pipeline(Broken())
        self.assertGreater(rep.get("needs_human", 0), 0)

    def test_prompt_has_only_relevant_glossary(self):
        cfg = make_project({}, TOML)
        s = build_system(cfg, "vi", {"apple": {"vi": "táo"}, "pear": {"vi": "lê"}}, "", "42 apples")
        self.assertIn("apple → táo", s)
        self.assertNotIn("pear", s)
