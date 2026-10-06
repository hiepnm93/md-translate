"""Translate digest units one LLM call each."""
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from mdtrans.backends import with_retry
from mdtrans.config import Config
from mdtrans.digest import out_file, unit_files
from mdtrans.glossary import relevant
from mdtrans.verify import has_prose

PROMPTS = Path(__file__).parent / "prompts"
LANG_NAMES = {"en": "English", "vi": "Vietnamese", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
              "ru": "Russian", "es": "Spanish", "pt": "Portuguese", "fr": "French", "de": "German",
              "it": "Italian", "th": "Thai", "id": "Indonesian", "fi": "Finnish"}


def _name(code: str) -> str:
    return LANG_NAMES.get(code, code)


def build_system(cfg: Config, lang: str, gloss: dict, rules: str, unit: str, extra: str = "") -> str:
    system = (PROMPTS / "translate.md").read_text(encoding="utf-8").format(
        source=_name(cfg.source_lang), target=_name(lang))
    if extra:
        system += "\n" + extra
    if rules.strip():
        system += "\nProject style rules:\n" + rules.strip() + "\n"
    terms = relevant(gloss, unit, lang)
    if terms:
        system += "\nGlossary (use these exact target terms):\n" + "".join(
            f"- {t} → {tr}" + (f" ({note})" if note else "") + "\n" for t, tr, note in terms)
    return system


_FENCE = re.compile(r"\A```[\w-]*\n(.*)\n```\s*\Z", re.S)


def fit(src: str, out: str) -> str:
    """Strip wrapper fences and re-apply the source unit's leading/trailing newlines."""
    out = out.strip()
    m = _FENCE.match(out)
    if m:
        out = m.group(1).strip()
    lead = src[: len(src) - len(src.lstrip("\n"))]
    trail = src[len(src.rstrip("\n")):]
    return lead + out.strip("\n") + trail


def translate_file(wd: Path, backend, cfg: Config, lang: str, gloss: dict, rules: str,
                   force: bool = False) -> tuple[int, int]:
    todo = [u for u in unit_files(wd) if force or not out_file(u).exists()]
    failed = 0

    def one(u: Path) -> bool:
        src = u.read_text(encoding="utf-8")
        if not has_prose(src):
            out_file(u).write_text(src, encoding="utf-8")
            return True
        try:
            out = with_retry(lambda: backend.complete(build_system(cfg, lang, gloss, rules, src), src))
        except Exception as e:
            print(f"  ! {wd.name}/{u.name}: {e}", file=sys.stderr)
            return False
        out_file(u).write_text(fit(src, out), encoding="utf-8")
        return True

    with ThreadPoolExecutor(max(1, cfg.concurrency)) as ex:
        failed = sum(not ok for ok in ex.map(one, todo))
    return len(todo) - failed, failed
