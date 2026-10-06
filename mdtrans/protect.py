"""Swap everything the LLM must not touch for ⟦Pn⟧ tokens, and back."""
import re

PH_RE = re.compile(r"⟦(P\d+)⟧")

# Order matters: block-level spans first, so later patterns never see their insides.
_BLOCKS = [
    re.compile(r"\A---\n.*?\n---[ \t]*\n", re.S),  # front matter
    re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$", re.M | re.S),  # fences
    re.compile(r"\$\$.*?\$\$", re.S),  # display math
    re.compile(r"<!--.*?-->", re.S),  # HTML comments
]
_REF_DEF = re.compile(r"^[ \t]*\[[^\]\n]+\]:[ \t]*\S.*$", re.M)
_INLINE = [
    re.compile(r"(`+)[^`\n]+?\1"),  # inline code
]
_LINK_TARGET = re.compile(r"\]\(([^)\s]+(?:\s+\"[^\"]*\")?)\)")
_LATE = [
    re.compile(r"<https?://[^>\s]+>"),  # autolinks
    re.compile(r"</?[A-Za-z][^>\n]*>"),  # HTML tags
    re.compile(r"https?://[^\s<>()\[\]\"']*[^\s<>()\[\]\"'.,;:!?]"),  # bare URLs
    re.compile(r"(?<![\\$\w])\$(?=\S)[^$\n]*?\S\$(?![\d$])"),  # inline math
]


def protect(text: str, extra: list[str]) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}

    def ph(s: str, raw: bool = False) -> str:
        key = f"P{len(mapping) + 1}"
        mapping[key] = s if raw else restore(s, mapping)  # expand nesting now; restore is one pass
        return f"⟦{key}⟧"

    def sub(rx: re.Pattern, t: str) -> str:
        return rx.sub(lambda m: ph(m.group(0)), t)

    text = PH_RE.sub(lambda m: ph(m.group(0), raw=True), text)  # literal token-like text in the source
    for rx in _BLOCKS:
        text = sub(rx, text)
    for pat in extra:
        text = sub(re.compile(pat, re.M), text)
    text = sub(_REF_DEF, text)
    for rx in _INLINE:
        text = sub(rx, text)
    text = _LINK_TARGET.sub(lambda m: "](" + ph(m.group(1)) + ")", text)
    for rx in _LATE:
        text = sub(rx, text)
    return text, mapping


def restore(text: str, mapping: dict[str, str]) -> str:
    return PH_RE.sub(lambda m: mapping.get(m.group(1), m.group(0)), text)
