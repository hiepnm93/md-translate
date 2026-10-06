import unittest

from mdtrans.digest import split_units
from mdtrans.protect import PH_RE, protect, restore

DOC = """---
title: Demo
---

# Title

Text with `inline code` and a [link text](https://ex.com/a "Title") plus <https://auto.link>.
Bare URL https://bare.example/path?q=1 here. Price $5 or $10, math $x^2$ ok.

```python
print("hi")
```

~~~
tilde fence
~~~

<div align="center">kept text</div>

$$
E = mc^2
$$

[ref]: https://ref.example
- 来源：DOI 10.1000/xyz
![alt text](img/a.png)
"""


class ProtectTest(unittest.TestCase):
    def test_round_trip(self):
        text, mapping = protect(DOC, [r"^- 来源：.*$"])
        self.assertEqual(restore(text, mapping), DOC)

    def test_hides_protected_shows_prose(self):
        text, _ = protect(DOC, [r"^- 来源：.*$"])
        for hidden in ("inline code", "https://ex.com", "print(", "tilde fence", "E = mc^2",
                       "x^2", "https://bare", "ref.example", "来源", "title: Demo", "img/a.png",
                       "<div", "auto.link"):
            self.assertNotIn(hidden, text, hidden)
        for shown in ("link text", "Price $5 or $10", "kept text", "alt text", "# Title"):
            self.assertIn(shown, text, shown)

    def test_numbering_unique(self):
        text, mapping = protect(DOC, [])
        ids = PH_RE.findall(text)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(mapping))


class SplitTest(unittest.TestCase):
    def test_lossless_and_heading_level(self):
        text = "intro\n\n# A\n\na\n\n## B\n\nb\n\n### C\n\nc\n"
        units = split_units(text, level=2, max_chars=10_000)
        self.assertEqual("".join(units), text)
        self.assertEqual([u.splitlines()[0] for u in units], ["intro", "# A", "## B"])

    def test_cap_on_blank_lines(self):
        text = "# H\n\n" + "\n\n".join("para %d " % i + "x" * 40 for i in range(10)) + "\n"
        units = split_units(text, level=1, max_chars=120)
        self.assertEqual("".join(units), text)
        self.assertGreater(len(units), 3)
        for u in units:
            self.assertLessEqual(len(u), 120)


class LiteralTokenTest(unittest.TestCase):
    def test_source_with_placeholder_like_text(self):
        doc = "Use `⟦P12⟧` tokens; bare ⟦P3⟧ and ⟦P1⟧ ⟦P1⟧ too.\n" + "".join(f"- [l{i}](u{i})\n" for i in range(20))
        text, mapping = protect(doc, [])
        self.assertEqual(restore(text, mapping), doc)
