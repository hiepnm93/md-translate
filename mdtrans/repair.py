"""Repair failing units: mechanical fixes first, then a constrained LLM pass."""
import re

_PH_VARIANTS = re.compile(r"(?:⟦|\[\[|【)\s*[Pp]\s*(\d+)\s*(?:⟧|\]\]|】)")


def mechanical(text: str) -> str:
    return _PH_VARIANTS.sub(r"⟦P\1⟧", text)
