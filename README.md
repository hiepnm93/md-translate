# md-translate

Translate Markdown with an LLM **unit by unit**, so the model only ever sees prose:
code, links, math, HTML and any line you mark stay byte-identical, and every unit is
hard-checked and repaired before a human reads it. Ships as a Claude Code plugin
(skill `translate-md`) plus a stdlib-only Python CLI.

Extracted from the translation pipeline of
[HowToLiveBetter](https://github.com/hiepnm93/HowToLiveBetter).

*Tiếng Việt: [bên dưới](#tiếng-việt).*

## Install

```text
/plugin marketplace add hiepnm93/md-translate
/plugin install md-translate@md-translate
```

Then ask Claude: *"translate docs/*.md into Vietnamese"*. Or use the CLI directly
(Python ≥ 3.11, no dependencies):

```bash
git clone https://github.com/hiepnm93/md-translate ~/md-translate
cd your-project
PYTHONPATH=~/md-translate python3 -m mdtrans init      # writes mdtrans.toml
PYTHONPATH=~/md-translate python3 -m mdtrans backends  # what can translate right now
PYTHONPATH=~/md-translate python3 -m mdtrans run --backend ssh:my-gpu-box
```

## How it works

```
source.md ─digest─▶ units/*.src.md (⟦Pn⟧ tokens) ─translate─▶ units/*.out.md
          ─verify─▶ report.json ─repair (mechanical → LLM, ≤3 rounds)─▶ ─assemble─▶ out.md
```

| Step | What it does |
|---|---|
| digest | Protects front matter, fenced code, inline code, link/image targets, URLs, HTML, math, reference definitions and `protect` regex lines as `⟦Pn⟧`; splits at headings ≤ `unit_heading_level`, capped by `max_unit_chars`. Lossless: re-assembling an untranslated digest gives the source byte for byte. |
| translate | One LLM call per unit; prompt = base rules + project `rules` + only the glossary terms present in that unit. Resumable, parallel (`concurrency`). |
| verify | HARD: placeholder multiset, heading levels, list-item count, every source number present (locale-tolerant), `banned` calques, glossary terms, leftover source script (e.g. Han in Vietnamese). |
| repair | Mechanical first (mangled tokens like `⟦ P12 ⟧`, `[[P12]]`), then a constrained LLM call with the exact problems; ≤ 8 units/round, 3 rounds; leftovers → `needs_human`. |
| assemble | Joins units, restores tokens, writes `out`. |

## Backends — chosen at translation time

`mdtrans backends` probes and recommends; you pass `--backend`:

| Spec | Uses | Config |
|---|---|---|
| `ssh:<host>` | `claude -p` on a remote machine | `MDTRANS_SSH_HOSTS=host[=model],…` |
| `openai[:<url>]` | any OpenAI-compatible API, llama-server | `MDTRANS_BASE_URL`, `MDTRANS_API_KEY`, `MDTRANS_MODEL` |
| `claude-cli` | local `claude -p` | `MDTRANS_MODEL` (optional) |
| `none` | verify + mechanical repair only | — |

Variables may live in the project's `.env`.

## Config

See the template written by `mdtrans init`, and [`examples/htlb/`](examples/htlb/) for a
real book (Chinese → Vietnamese, protected citation lines, glossary, style rules).

## Limits

Markdown only. Verify checks structure and numbers, not meaning: read a sample before
publishing, and fact-check anything the rules ask the model to *add*.

---

## Tiếng Việt

**md-translate** dịch Markdown bằng LLM theo từng đơn vị nhỏ. Mô hình chỉ thấy phần chữ:
code, link, công thức, HTML và các dòng bạn đánh dấu được giữ nguyên từng byte. Mỗi
đơn vị đều được kiểm tra cứng (token, tiêu đề, số mục list, con số, thuật ngữ, cụm dịch
sát chữ bị cấm, chữ nguồn còn sót) và tự sửa trước khi đến tay người đọc.

Cài trong Claude Code:

```text
/plugin marketplace add hiepnm93/md-translate
/plugin install md-translate@md-translate
```

Rồi bảo Claude: *"dịch docs/*.md sang tiếng Việt"*. Skill sẽ dò các backend đang dùng
được (máy remote qua SSH, API tương thích OpenAI, `claude` local), đề xuất một cái và
hỏi bạn chọn trước khi dịch. Chạy lại an toàn: đơn vị đã dịch sẽ bỏ qua. Đơn vị sửa 3
vòng vẫn lỗi được đánh dấu `needs_human` để bạn xem.
