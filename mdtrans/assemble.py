"""Join translated units and restore protected spans."""
import json
from pathlib import Path

from mdtrans.digest import out_file, unit_files
from mdtrans.protect import restore


def assemble_file(wd: Path) -> str:
    missing = [u.name for u in unit_files(wd) if not out_file(u).exists()]
    if missing:
        raise ValueError(f"{wd.name}: {len(missing)} untranslated units, e.g. {missing[:3]}")
    mapping = json.loads((wd / "placeholders.json").read_text(encoding="utf-8"))
    return restore("".join(out_file(u).read_text(encoding="utf-8") for u in unit_files(wd)), mapping)
