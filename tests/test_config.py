import json
import tomllib
import unittest

from mdtrans import config, glossary
from mdtrans.digest import digest_file
from tests.helpers import make_project

TOML = """
source_lang = "zh"
targets = ["vi"]
files = ["book/*.md"]
out = "book/{lang}/{name}"
glossary = "g.json"
"""


class ConfigTest(unittest.TestCase):
    def test_template_parses(self):
        data = tomllib.loads(config.TEMPLATE)
        self.assertIn("source_lang", data)

    def test_sources_and_out_path(self):
        cfg = make_project({"book/01-a.md": "# A\n", "book/vi/01-a.md": "old\n"}, TOML)
        srcs = config.sources(cfg)
        self.assertEqual([s.name for s in srcs], ["01-a.md"])
        self.assertEqual(config.out_path(cfg, srcs[0], "vi"), cfg.root / "book/vi/01-a.md")

    def test_unknown_key_rejected(self):
        with self.assertRaises(ValueError):
            make_project({}, TOML + 'oops = 1\n')

    def test_glossary_relevant(self):
        cfg = make_project({"g.json": json.dumps({"成本": {"vi": "Chi phí"}, "收益": {"vi": "Lợi ích"}})}, TOML)
        g = glossary.load(cfg.root / "g.json")
        self.assertEqual(glossary.relevant(g, "这是成本", "vi"), [("成本", "Chi phí", "")])


class DigestFileTest(unittest.TestCase):
    def test_keeps_outputs_until_source_changes(self):
        cfg = make_project({"book/01.md": "# A\n\na\n\n### B\n\nb\n"}, TOML)
        src = config.sources(cfg)[0]
        wd = digest_file(cfg, src, "vi")
        units = sorted((wd / "units").glob("*.src.md"))
        self.assertEqual(len(units), 2)
        out = units[0].with_name(units[0].name.replace(".src.", ".out."))
        out.write_text("x", encoding="utf-8")
        digest_file(cfg, src, "vi")
        self.assertTrue(out.exists())
        src.write_text("# A changed\n", encoding="utf-8")
        digest_file(cfg, src, "vi")
        self.assertFalse(out.exists())
