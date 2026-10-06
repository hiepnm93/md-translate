"""Split protected Markdown into translation units and persist them to a workdir."""
import re

_HEADING = re.compile(r"^(#{1,6})[ \t]")
_PARA = re.compile(r"(?<=\n\n)")


def split_units(text: str, level: int, max_chars: int) -> list[str]:
    """Lossless split: "".join(result) == text."""
    sections: list[str] = []
    cur = ""
    for line in text.splitlines(keepends=True):
        m = _HEADING.match(line)
        if m and len(m.group(1)) <= level and cur:
            sections.append(cur)
            cur = ""
        cur += line
    if cur:
        sections.append(cur)

    units: list[str] = []
    for sec in sections:
        if len(sec) <= max_chars:
            units.append(sec)
            continue
        buf = ""
        for para in _PARA.split(sec):
            if buf and len(buf) + len(para) > max_chars:
                units.append(buf)
                buf = ""
            buf += para
        if buf:
            units.append(buf)
    return units
