"""Split protected Markdown into translation units and persist them to a workdir."""
import hashlib
import json
import re
import shutil
from pathlib import Path

from mdtrans.config import Config, workdir_for
from mdtrans.protect import protect

FORMAT = 2  # bump when protect/split output changes, so stale workdirs are rebuilt
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


def unit_files(wd: Path) -> list[Path]:
    return sorted((wd / "units").glob("*.src.md"))


def out_file(src_unit: Path) -> Path:
    return src_unit.with_name(src_unit.name.replace(".src.md", ".out.md"))


def digest_file(cfg: Config, src: Path, lang: str) -> Path:
    """Write units + placeholder map; keep existing outputs while source and split settings match."""
    text = src.read_text(encoding="utf-8")
    key = json.dumps([FORMAT, text, cfg.protect, cfg.unit_heading_level, cfg.max_unit_chars])
    digest = hashlib.sha256(key.encode()).hexdigest()
    wd = workdir_for(cfg, src, lang)
    meta = wd / "meta.json"
    if meta.exists() and json.loads(meta.read_text())["hash"] == digest:
        return wd
    shutil.rmtree(wd, ignore_errors=True)
    (wd / "units").mkdir(parents=True)
    protected, mapping = protect(text, cfg.protect)
    units = split_units(protected, cfg.unit_heading_level, cfg.max_unit_chars)
    width = max(3, len(str(len(units))))
    for i, u in enumerate(units, 1):
        (wd / "units" / f"{i:0{width}d}.src.md").write_text(u, encoding="utf-8")
    (wd / "placeholders.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
    rel = src.relative_to(cfg.root).as_posix()
    meta.write_text(json.dumps({"source": rel, "lang": lang, "hash": digest, "units": len(units)}), encoding="utf-8")
    return wd
