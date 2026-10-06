"""Project config (mdtrans.toml) and path helpers."""
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

NAME = "mdtrans.toml"

TEMPLATE = '''# md-translate project config
source_lang = "en"              # language of the source files
targets = ["vi"]                # target languages
files = ["docs/*.md"]           # globs relative to this file
out = "{lang}/{path}"           # output template: {lang} {path} {dir} {name} {stem}
# glossary = "glossary.json"    # {"term": {"vi": "thuật ngữ", "note": "optional"}}
# rules = "rules/{lang}.md"     # free-text style rules per target language
unit_heading_level = 3          # new unit at headings this deep or shallower
max_unit_chars = 6000           # long sections split at blank lines
protect = []                    # regexes for lines kept byte-identical, e.g. '^- Source: .*$'
# banned = { vi = ['\\bđược tiến hành\\b'] }   # calques that fail verify
workdir = ".mdtrans"            # state dir; add to .gitignore
concurrency = 2                 # parallel LLM calls
'''


@dataclass
class Config:
    root: Path
    source_lang: str
    targets: list[str]
    files: list[str]
    out: str = "{lang}/{path}"
    glossary: str | None = None
    rules: str | None = None
    unit_heading_level: int = 3
    max_unit_chars: int = 6000
    protect: list[str] = field(default_factory=list)
    banned: dict[str, list[str]] = field(default_factory=dict)
    workdir: str = ".mdtrans"
    concurrency: int = 2


def load(path: Path) -> Config:
    path = Path(path).resolve()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Config)} - {"root"}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"{path}: unknown keys {sorted(unknown)}")
    return Config(root=path.parent, **data)


def find(start: Path) -> Path:
    for d in [start.resolve(), *start.resolve().parents]:
        if (d / NAME).exists():
            return d / NAME
    raise FileNotFoundError(f"no {NAME} in {start} or its parents (run: mdtrans init)")


def _fmt(cfg: Config, template: str, src: Path, lang: str) -> Path:
    rel = src.relative_to(cfg.root)
    return cfg.root / template.format(
        lang=lang, path=rel.as_posix(), dir=rel.parent.as_posix(), name=rel.name, stem=rel.stem
    )


def out_path(cfg: Config, src: Path, lang: str) -> Path:
    return _fmt(cfg, cfg.out, src, lang)


def sources(cfg: Config) -> list[Path]:
    found = {p.resolve() for g in cfg.files for p in cfg.root.glob(g) if p.is_file()}
    state = (cfg.root / cfg.workdir).resolve()
    found = {p for p in found if state not in p.parents}
    outs = {out_path(cfg, p, lang).resolve() for p in found for lang in cfg.targets}
    return sorted(found - outs)


def workdir_for(cfg: Config, src: Path, lang: str) -> Path:
    slug = src.relative_to(cfg.root).as_posix().replace("/", "__")
    return cfg.root / cfg.workdir / lang / slug


def rules_text(cfg: Config, lang: str) -> str:
    if not cfg.rules:
        return ""
    p = cfg.root / cfg.rules.format(lang=lang)
    return p.read_text(encoding="utf-8") if p.exists() else ""
