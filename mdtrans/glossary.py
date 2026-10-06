"""Glossary: {"source term": {"<lang>": "target term", "note": "..."}}."""
import json
from pathlib import Path


def load(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def relevant(gloss: dict[str, dict[str, str]], text: str, lang: str) -> list[tuple[str, str, str]]:
    return [(t, e[lang], e.get("note", "")) for t, e in gloss.items() if lang in e and t in text]
