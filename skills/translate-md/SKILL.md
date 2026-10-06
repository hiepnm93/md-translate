---
name: translate-md
description: Translate Markdown files (books, docs, READMEs) into other languages with an LLM, unit by unit, keeping code/links/math byte-identical and hard-verifying every unit (placeholders, headings, list items, numbers, glossary, banned calques, leftover source script). Use when the user asks to translate .md files or a docs/book folder, to continue or repair such a translation, or to check translation quality.
---

# translate-md

The CLI lives in this plugin. Plugin root = two directories above this SKILL.md
(the "Base directory for this skill" shown when the skill loads, minus `skills/translate-md`).
Run every command from the project being translated:

```bash
PYTHONPATH=<plugin-root> python3 -m mdtrans <command>
```

Needs Python ≥ 3.11, no packages.

## Flow

1. **Config.** Look for `mdtrans.toml` in the project (or a parent). If missing, ask the
   user for: source language, target language(s), which files (globs), output path
   template. Then `mdtrans init`, edit the file, and add `.mdtrans/` to `.gitignore`.
   Optional: `glossary` (JSON `{"term": {"vi": "thuật ngữ", "note": "…"}}`), `rules`
   (free-text style rules per language), `protect` (regexes for whole lines to keep
   byte-identical, e.g. source citations), `banned` (calque regexes per language).
2. **Pick the backend — the translator decides.** Run `mdtrans backends`. It lists every
   candidate (★ recommended, ✓ usable, ✗ not reachable): `ssh:<host>` (claude -p on a
   remote box, hosts from `MDTRANS_SSH_HOSTS=host[=model],…`), `openai:<url>`
   (OpenAI-compatible endpoint / llama-server; `MDTRANS_BASE_URL`, `MDTRANS_API_KEY`,
   `MDTRANS_MODEL`, may live in the project `.env`), `claude-cli` (local). Show the list
   and ask the user which one to use (recommend the ★ one; remote hosts keep heavy work
   off this machine). Never pick silently when more than one is usable.
3. **Translate.** `mdtrans run --backend <spec> [--model M] [--lang L] [--only 'glob']`.
   For more than a few files run it in the background and check `mdtrans status`.
   Re-running is safe: finished units are skipped (`--force` to redo). Try one small
   file first and show the user a sample before doing the rest.
4. **Review failures.** `mdtrans verify` prints failing units as `file#unit: codes`.
   Units marked `needs_human` survived 3 repair rounds. Open
   `.mdtrans/<lang>/<file-slug>/units/<unit>.src.md` and `.out.md`, fix the `.out.md`
   with the user, then `mdtrans verify` and `mdtrans assemble`.
5. **Before committing**, ask the user to read a sample by eye. Verify catches
   structural and numeric errors, not wrong meaning.

## Notes

- Units: split at headings ≤ `unit_heading_level`, capped by `max_unit_chars`.
- `⟦Pn⟧` tokens stand for protected spans; they must survive translation exactly once.
- If the project rules ask the model to *add* facts (local law, prices, institutions),
  fact-check those additions separately — small models invent them.
- Only verify/repair (no LLM): `mdtrans repair --backend none`.
