"""Repair failing units: mechanical fixes first, then a constrained LLM pass."""
import json
import re
from collections import Counter
from pathlib import Path

from mdtrans.backends import with_retry
from mdtrans.config import Config
from mdtrans.translate import PROMPTS, _name, build_system, fit
from mdtrans.verify import verify_file

_PH_VARIANTS = re.compile(r"(?:⟦|\[\[|【)\s*[Pp]\s*(\d+)\s*(?:⟧|\]\]|】)")


def mechanical(text: str) -> str:
    return _PH_VARIANTS.sub(r"⟦P\1⟧", text)


_EXPLAIN = {
    "empty": "the translation is empty",
    "headings": "heading count or levels differ from the source",
    "list_items": "number of list items differs from the source",
    "leftover_script": "untranslated source-language text remains",
}


def explain(code: str) -> str:
    kind, _, rest = code.partition(":")
    if kind == "placeholder":
        how, _, ph = rest.partition(":")
        return f"token ⟦{ph}⟧ is {'missing — put it back exactly once' if how == 'missing' else 'extra or duplicated — keep exactly one'}"
    if kind == "number":
        return f"number {rest} from the source is missing"
    if kind == "banned":
        return f"avoid the phrasing matching /{rest}/"
    if kind == "glossary":
        return f"use the glossary term for '{rest}'"
    return _EXPLAIN.get(code, code)


def repair_file(wd: Path, backend, cfg: Config, lang: str, gloss: dict, rules: str,
                rounds: int = 3, per_round: int = 8) -> dict:
    rep = verify_file(wd, cfg, lang, gloss)
    for _ in range(rounds):
        failing = [uid for uid, u in rep["units"].items() if u["status"] == "fail"]
        if not failing:
            break
        for uid in failing:
            of = wd / "units" / f"{uid}.out.md"
            of.write_text(mechanical(of.read_text(encoding="utf-8")), encoding="utf-8")
        rep = verify_file(wd, cfg, lang, gloss)
        failing = [uid for uid, u in rep["units"].items() if u["status"] == "fail"]
        if not failing or backend is None:
            break
        for uid in failing[:per_round]:
            sf, of = wd / "units" / f"{uid}.src.md", wd / "units" / f"{uid}.out.md"
            src, draft = sf.read_text(encoding="utf-8"), of.read_text(encoding="utf-8")
            extra = (PROMPTS / "repair.md").read_text(encoding="utf-8").format(target=_name(lang))
            user = (f"<source>\n{src}\n</source>\n\n<draft>\n{draft}\n</draft>\n\n<problems>\n"
                    + "".join(f"- {explain(c)}\n" for c in rep["units"][uid]["failures"]) + "</problems>")
            try:
                out = with_retry(lambda: backend.complete(build_system(cfg, lang, gloss, rules, src, extra), user))
            except Exception:
                continue
            of.write_text(mechanical(fit(src, out)), encoding="utf-8")
        rep = verify_file(wd, cfg, lang, gloss)
    for u in rep["units"].values():
        if u["status"] == "fail":
            u["status"] = "needs_human"
    rep = {"units": rep["units"], **Counter(u["status"] for u in rep["units"].values())}
    (wd / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep
