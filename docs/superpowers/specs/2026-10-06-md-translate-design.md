# md-translate — design

Date: 2026-10-06. Origin: the `translate/` pipeline in hiepnm93/HowToLiveBetter (HTLB),
generalized into a standalone Claude Code plugin for translating any Markdown.

## Goal

Translate Markdown documents (books, docs, READMEs) between languages with an LLM,
reliably: the model only ever sees prose, everything that must stay byte-identical is
protected, and every output is mechanically verified and repaired before a human looks.

Non-goals (v1): LaTeX/other formats, LanguageTool, readability scoring, golden/mutation
calibration research, site/ebook building.

## Packaging

Public repo `hiepnm93/md-translate`, installable as a Claude Code plugin marketplace:

```
.claude-plugin/marketplace.json     # marketplace with one plugin: md-translate
.claude-plugin/plugin.json
skills/translate-md/SKILL.md        # how Claude drives the CLI + asks the translator
mdtrans/                            # Python package, stdlib only, Python >= 3.11
  cli.py config.py digest.py protect.py translate.py backends.py
  assemble.py verify.py repair.py glossary.py status.py prompts/
tests/                              # unittest, stdlib only
examples/htlb/                      # profile reproducing HTLB conventions
.github/workflows/ci.yml            # python -m unittest
```

Run as `python3 -m mdtrans <cmd>` (no install step); SKILL.md points at
`${CLAUDE_PLUGIN_ROOT}`.

## Project config — `mdtrans.toml`

Lives in the project being translated (`mdtrans init` writes a commented template).

```toml
source_lang = "zh"
targets = ["vi"]
files = ["book/*.md"]                 # globs, relative to the config file
out = "book/{lang}/{name}"            # output path template
glossary = "glossary.json"            # optional: {"term": {"vi": "...", "note": "..."}}
rules = "rules/{lang}.md"             # optional: free-text style rules per target
unit_heading_level = 3                # split at headings of this depth or shallower
max_unit_chars = 6000                 # hard cap; long sections split at paragraph breaks
protect = ['^- 来源：.*$']             # extra regexes for whole lines kept byte-identical
banned = {vi = ['\bđược tiến hành\b']} # calques that fail verify
workdir = ".mdtrans"                  # gitignored state
concurrency = 2
```

## Pipeline

State per file lives in `<workdir>/<lang>/<file-slug>/`: `units/NNN.src.md`,
`units/NNN.out.md`, `placeholders.json`, `report.json`. Each step is idempotent and
resumable; `run` chains them.

1. **digest** — parse the source into units at headings ≤ `unit_heading_level`, then
   cap by `max_unit_chars` at blank lines (never inside a fenced block). Replace with
   placeholders `⟦P12⟧`: front matter, fenced/indented code, inline code, URLs and link
   targets (link *text* stays translatable), HTML tags, `$…$`/`$$…$$` math, reference
   definitions, and lines matching `protect`. Placeholder map → `placeholders.json`.
2. **translate** — one LLM call per unit. Prompt = base rules (`prompts/translate.md`:
   keep every `⟦Pn⟧` exactly once, keep Markdown structure, don't add/remove content,
   keep numbers) + project `rules` + only the glossary entries whose source term occurs
   in the unit. Skips units whose `.out.md` exists unless `--force`. Bounded parallelism.
3. **assemble** — concatenate unit outputs, restore placeholders, write to `out`.
4. **verify** — per unit and per file, HARD failures:
   - placeholder set identical (none lost, duplicated, or invented);
   - heading count/levels and list-item count equal to source;
   - every number in the source appears in the output (locale-normalized: `1,5`≈`1.5`,
     thin/NBSP thousands separators);
   - no `banned` pattern; glossary target term used where the source term occurs;
   - no leftover source-script text (e.g. Han characters in a `vi` output) outside
     placeholders.
   Writes `report.json`; exit 1 if any HARD failure.
5. **repair** — mechanical first (number format normalization, mangled placeholder
   spacing like `⟦ P12 ⟧`, collapsed list labels); then for still-failing units an LLM
   repair call that gets the source, current draft, and the exact failures. Max 3 rounds,
   ≤ 8 units per round; units still failing are marked `needs_human` in the report.
6. **status** — table of files × langs: units done / failing / needs_human.

Optional `--fact-check` (v1: flag + hook only): when a project's rules ask the model to
*add* content (e.g. HTLB's «Tại Việt Nam» notes), list those additions for a separate
review pass. Rationale: glm-flash fabricated ~25% of Vietnamese legal facts in HTLB.

## Backends — chosen by the translator at run time

`mdtrans backends` probes and prints what is usable right now, with a recommendation:

- **openai** — any OpenAI-compatible endpoint: `MDTRANS_BASE_URL` / `MDTRANS_API_KEY` /
  `MDTRANS_MODEL` from env or `.env`, plus a probe of `http://127.0.0.1:8080/v1/models`
  (llama-server).
- **claude-cli** — local `claude -p` (model from `MDTRANS_MODEL` or CLI default).
- **claude-ssh** — `ssh <host> bash -lc 'claude -p …'` for hosts listed in
  `MDTRANS_SSH_HOSTS` (e.g. `100.64.0.11` with model `glm-5.3-flash`); probed with a
  5 s `ssh -o BatchMode=yes <host> true`.

Recommendation order: a reachable dedicated endpoint/host first (offloads heavy work),
then local CLI. `translate`/`repair`/`run` take `--backend NAME [--model M]`; with no
flag and more than one option, the CLI exits asking for a choice. SKILL.md tells Claude
to run `backends`, show the list, and ask the translator before translating.

Errors: transient backend errors retry 3× with backoff; a unit that keeps failing is
recorded in the report and the run continues.

## SKILL.md flow

1. Find or create `mdtrans.toml` (ask source/target langs and files if creating).
2. `mdtrans backends` → present options + recommendation → translator picks.
3. `mdtrans run --lang L --backend B` (in background for big jobs) → `status`.
4. Show verify report; for `needs_human` units, show source vs draft and fix with the
   translator; re-run `verify`.
5. Remind: review a sample by eye before committing.

## Testing

stdlib `unittest`, no network: protect/digest round-trip (assemble(digest(x)) == x with
identity translation), placeholder edge cases (nested code in lists, links with titles,
math), verify detectors (each HARD rule has a failing and passing case), mechanical
repair, and an end-to-end `run` against a fake backend. CI runs on every push. A real
translation smoke test (one short file) is run manually on the .11 host.

## Relationship to HTLB

HTLB keeps its own `translate/` unchanged for now. `examples/htlb/` shows the
equivalent `mdtrans.toml` + glossary/rules so HTLB can migrate later.
