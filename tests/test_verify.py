import unittest

from mdtrans.config import Config
from mdtrans.repair import mechanical
from mdtrans.verify import check_unit

CFG = Config(root=None, source_lang="zh", targets=["vi"], files=[], banned={"vi": [r"\bđược tiến hành\b"]})
GLOSS = {"成本": {"vi": "Chi phí"}}
SRC = "### 1. 戴头盔 ⟦P1⟧\n\n- 成本：3 元\n- 收益：死亡风险降低 40%，1,234 人 ⟦P2⟧\n"
GOOD = "### 1. Đội mũ bảo hiểm ⟦P1⟧\n\n- Chi phí: 3 đồng\n- Lợi ích: nguy cơ tử vong giảm 40%, 1 234 người ⟦P2⟧\n"


def check(out, src=SRC, lang="vi", cfg=CFG):
    return check_unit(src, out, cfg, lang, GLOSS)


class VerifyTest(unittest.TestCase):
    def test_good(self):
        self.assertEqual(check(GOOD), [])

    def test_placeholder(self):
        self.assertIn("placeholder:missing:P2", check(GOOD.replace(" ⟦P2⟧", "")))
        self.assertIn("placeholder:extra:P1", check(GOOD + "⟦P1⟧"))

    def test_structure(self):
        self.assertIn("headings", check(GOOD.replace("### ", "## ")))
        self.assertIn("list_items", check(GOOD.replace("- Chi phí", "Chi phí")))

    def test_numbers(self):
        self.assertIn("number:40", check(GOOD.replace("40%", "bốn mươi phần trăm")))
        self.assertEqual(check(GOOD.replace("1 234", "1.234")), [])
        self.assertEqual(check_unit("rate 1,5 %", "tỉ lệ 1.5 %", CFG, "vi", {}), [])

    def test_banned_glossary_script_empty(self):
        self.assertIn(r"banned:\bđược tiến hành\b", check(GOOD + "được tiến hành\n"))
        self.assertIn("glossary:成本", check(GOOD.replace("Chi phí", "Giá")))
        self.assertIn("leftover_script", check(GOOD.replace("Đội", "戴")))
        self.assertEqual(check_unit("漢字", "漢字", CFG, "ja", {}), [])
        self.assertIn("empty", check("  \n"))


class MechanicalTest(unittest.TestCase):
    def test_placeholder_variants(self):
        self.assertEqual(mechanical("a ⟦ P12 ⟧ [[P3]] 【P4】 ⟦p5⟧"), "a ⟦P12⟧ ⟦P3⟧ ⟦P4⟧ ⟦P5⟧")
