import tempfile
from pathlib import Path

from mdtrans import config


def make_project(files: dict[str, str], toml: str) -> config.Config:
    root = Path(tempfile.mkdtemp(prefix="mdtrans-test-"))
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    (root / "mdtrans.toml").write_text(toml, encoding="utf-8")
    return config.load(root / "mdtrans.toml")
