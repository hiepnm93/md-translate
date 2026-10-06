# md-translate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standalone Claude Code plugin + stdlib Python CLI (`python3 -m mdtrans`) that translates Markdown unit-by-unit with protected spans, hard verify, and mechanical-first repair.

**Architecture:** Pure functions per stage (protect → split → translate → assemble → verify → repair) over a per-file workdir on disk; `cli.py` wires them; backends are small classes with `complete(system, user) -> str`. Tests inject a fake backend.

**Tech Stack:** Python ≥ 3.11 stdlib only (`tomllib`, `urllib`, `subprocess`, `concurrent.futures`, `unittest`).

## Global Constraints

- Python >= 3.11, stdlib only, no install step: run as `python3 -m mdtrans`.
- Placeholder token format: `⟦P<n>⟧` (n = 1-based int, unique per source file).
- State dir: `<workdir>/<lang>/<file-slug>/` with `units/NNN.src.md`, `units/NNN.out.md`, `placeholders.json`, `meta.json`, `report.json`.
- Repair: max 3 rounds, ≤ 8 LLM-repaired units per round; leftovers = `needs_human`.
- Backend env: `MDTRANS_BASE_URL`, `MDTRANS_API_KEY`, `MDTRANS_MODEL`, `MDTRANS_SSH_HOSTS` (`host[=model],…`).
- Transient backend errors: 3 retries with backoff.

## File map

| File | Responsibility |
|---|---|
| `mdtrans/protect.py` | `protect(text, extra) -> (text, map)`, `restore(text, map)`, `PH_RE` |
| `mdtrans/digest.py` | `split_units(text, level, max_chars)`, `digest_file(cfg, src, lang) -> Path` |
| `mdtrans/config.py` | `Config`, `load(path)`, `find(start)`, `TEMPLATE`, `sources(cfg)`, `out_path(cfg, src, lang)`, `workdir_for(cfg, src, lang)` |
| `mdtrans/glossary.py` | `load(path)`, `relevant(gloss, text, lang)` |
| `mdtrans/backends.py` | `OpenAI`, `ClaudeCLI`, `ClaudeSSH`, `probe()`, `make(name, model)`, `with_retry` |
| `mdtrans/translate.py` | `build_prompt`, `clean_output`, `translate_file(wd, backend, cfg, lang, force)` |
| `mdtrans/assemble.py` | `assemble_file(wd) -> str` |
| `mdtrans/verify.py` | `check_unit(src, out, cfg, lang, gloss) -> list[str]`, `verify_file(wd, cfg, lang, gloss) -> dict` |
| `mdtrans/repair.py` | `mechanical(text) -> str`, `repair_file(wd, backend, cfg, lang, gloss) -> dict` |
| `mdtrans/cli.py`, `__main__.py` | subcommands: init, backends, digest, translate, assemble, verify, repair, run, status |
| `mdtrans/prompts/{translate,repair}.md` | base prompts |
| `skills/translate-md/SKILL.md`, `.claude-plugin/*` | plugin packaging |
| `tests/test_*.py` | unittest per module + e2e with fake backend |

### Task 1: protect + split (lossless round-trip)

Produces `protect(text, extra) -> (str, dict)`, `restore(text, mapping) -> str`, `split_units(text, level, max_chars) -> list[str]` with `"".join(units) == text`.

- [ ] Tests: round-trip on fixture with front matter, ``` and ~~~ fences, inline code, links with titles, autolinks, bare URLs, HTML tags, `$x$`, `$$…$$`, reference defs, `extra` regex line; `$5 or $10` not math; link text stays visible; split respects heading level, lossless, caps on blank lines.
- [ ] Fail → implement → pass → commit.

### Task 2: config + glossary + digest_file

- [ ] Tests: template TOML loads; `out_path` placeholders `{lang} {name} {stem} {path}`; `relevant()` only present terms; digest keeps outs when source unchanged, wipes when changed.
- [ ] Implement → pass → commit.

### Task 3: verify + mechanical repair

Failure codes: `placeholder:*`, `headings`, `list_items`, `number:<n>`, `banned:<pat>`, `glossary:<term>`, `leftover_script`, `empty`.

- [ ] Tests: pass + fail case per code; numbers tolerate `1,5`/`1.5`, `1 234`/`1,234`; Han leftovers flagged for zh→vi only; mechanical fixes `⟦ P12 ⟧`, `[[P12]]`, `【P12】`, `⟦p12⟧`.
- [ ] Implement → pass → commit.

### Task 4: backends + translate + assemble + repair loop + e2e

- [ ] Tests (fake backends): identity → output == source, all ok; drops a placeholder once → repaired; always broken → `needs_human`; prompt contains only relevant glossary.
- [ ] Implement → pass → commit.

### Task 5: CLI, prompts, packaging, CI, example, README

- [ ] `python3 -m mdtrans --help`; `init`, `backends`, `status` work.
- [ ] SKILL.md, marketplace/plugin JSON, CI, `examples/htlb/`, README.
- [ ] Smoke: real translation of a short file via claude-ssh on 100.64.0.11 (glm-5.3-flash). Create public repo, push.
