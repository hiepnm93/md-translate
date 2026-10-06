"""Hard checks on a translated unit (both sides still carry ⟦Pn⟧ placeholders)."""
import json
import re
from collections import Counter
from pathlib import Path

from mdtrans.config import Config
from mdtrans.digest import out_file, unit_files
from mdtrans.glossary import relevant
from mdtrans.protect import PH_RE

_HEADING = re.compile(r"^(#{1,6})\s", re.M)
_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+", re.M)
_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_GROUP_SEP = re.compile(r"(?<=\d)[ \u00a0\u202f\u2009](?=\d{3}\b)")
_FAMILY = {"zh": "han", "ja": "han", "ko": "hangul", "ru": "cyr", "uk": "cyr", "bg": "cyr",
           "ar": "arab", "fa": "arab", "th": "thai", "el": "greek", "he": "hebrew"}
_SCRIPT = {"han": r"[\u4e00-\u9fff]", "hangul": r"[\uac00-\ud7af]", "cyr": r"[\u0400-\u04ff]",
           "arab": r"[\u0600-\u06ff]", "thai": r"[\u0e00-\u0e7f]", "greek": r"[\u0370-\u03ff]",
           "hebrew": r"[\u0590-\u05ff]"}


def _numbers(text: str) -> set[str]:
    text = _GROUP_SEP.sub("", PH_RE.sub(" ", text))
    return {re.sub(r"\D", "", n) for n in _NUM.findall(text)}


def has_prose(text: str) -> bool:
    return bool(re.search(r"[^\W\d_]", PH_RE.sub("", text)))


def check_unit(src: str, out: str, cfg: Config, lang: str, gloss: dict) -> list[str]:
    if has_prose(src) and not out.strip():
        return ["empty"]
    fails = []
    a, b = Counter(PH_RE.findall(src)), Counter(PH_RE.findall(out))
    fails += [f"placeholder:missing:{k}" for k in sorted(a - b)]
    fails += [f"placeholder:extra:{k}" for k in sorted(b - a)]
    if [len(h) for h in _HEADING.findall(src)] != [len(h) for h in _HEADING.findall(out)]:
        fails.append("headings")
    if len(_LIST.findall(src)) != len(_LIST.findall(out)):
        fails.append("list_items")
    fails += [f"number:{n}" for n in sorted(_numbers(src) - _numbers(out))]
    fails += [f"banned:{p}" for p in cfg.banned.get(lang, []) if re.search(p, out, re.I)]
    fails += [f"glossary:{t}" for t, target, _ in relevant(gloss, src, lang) if target.lower() not in out.lower()]
    fam = _FAMILY.get(cfg.source_lang)
    if fam and fam != _FAMILY.get(lang) and re.search(_SCRIPT[fam], PH_RE.sub("", out)):
        fails.append("leftover_script")
    return fails


def verify_file(wd: Path, cfg: Config, lang: str, gloss: dict) -> dict:
    report_path = wd / "report.json"
    old = json.loads(report_path.read_text()) if report_path.exists() else {"units": {}}
    units = {}
    for su in unit_files(wd):
        uid = su.name.split(".")[0]
        of = out_file(su)
        if not of.exists():
            units[uid] = {"status": "untranslated", "failures": []}
            continue
        fails = check_unit(su.read_text(encoding="utf-8"), of.read_text(encoding="utf-8"), cfg, lang, gloss)
        status = "ok" if not fails else ("needs_human" if old["units"].get(uid, {}).get("status") == "needs_human" else "fail")
        units[uid] = {"status": status, "failures": fails}
    report = {"units": units, **Counter(u["status"] for u in units.values())}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report
