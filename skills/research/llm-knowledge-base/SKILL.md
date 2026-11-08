---
name: llm-knowledge-base
description: Export Hermes sessions to a searchable markdown knowledge base with document-level and paragraph-level search.
version: 1.0.0
platforms: [windows, linux, macos]
---

# LLM Knowledge Base

Export Hermes Agent sessions from `state.db` into a clean, searchable markdown knowledge base. Two search modes: document-level (list matching files) and paragraph-level (exact paragraphs with anchor links). Built to scale across multiple LLM sources (GPT, Gemini, Grok, etc.).

## Trigger

Use this skill when the user:
- Wants to export, search, or browse their Hermes chat history
- Asks about building a knowledge base from LLM conversations
- Needs to find specific content from past sessions
- Mentions `LLM-KNOWLEDGE-BASE`, `export.py`, or `search.py`
- Asks to find chats that discuss a **specific project** on disk (e.g. "find chats about `G:\_My_Programming\FOO`")
- Wants to write a structured summary of one or more past sessions

## Project location

```
G:\_My_Programming\LLM-KNOWLEDGE-BASE\
├── index.md              # auto-generated catalogue table
├── export.py             # state.db → clean .md files
├── search.py             # two-mode search engine
├── sd.bat                # shortcut: sd <query>
├── sp.bat                # shortcut: sp <query>
└── chats/
    └── hermes/           # exported sessions (NN_slug.md)
```

## Export workflow

```bash
cd G:/_My_Programming/LLM-KNOWLEDGE-BASE
python export.py
```

This reads `%LOCALAPPDATA%/hermes/state.db`, filters out subagent-only sessions and system noise (model-switch announcements, empty tool results), and writes clean markdown files to `chats/hermes/`.

Each exported file:
- UTF-8 with BOM (mandatory — see pitfalls)
- YAML frontmatter with `title`, `source`, `session_id`, `model`, `date`, `topics`, `message_count`
- Messages formatted as `### Пользователь` / `### Ассистент` / `### Инструмент`
- HTML anchors `<a id="msg-N"></a>` on every message for direct navigation
- Tool calls summarised as `*(инструменты: name1, name2)*` instead of raw JSON
- Auto-numbered: `01_slug.md`, `02_slug.md`...

`index.md` is regenerated on every export — a table of all chats with topics.

## Search

### Document-level (`--docs`)
```bash
python search.py --docs nsfw              # AND search
python search.py --docs "git stash"       # phrase
python search.py --docs "" --topic проза  # all docs by topic
python search.py --docs python --model deepseek
sd nsfw                                    # shortcut
```
Returns: ranked list of matching files with model, date, message count, match count, snippet.

### Paragraph-level (`--paras`)
```bash
python search.py --paras nsfw --context 2
python search.py --paras nsfw рассказ --any     # OR search
python search.py --paras python --model deepseek --any -n 10
sp nsfw --any -n 10                               # shortcut
```
Returns: specific paragraphs with:
- **Anchor link** `chats/hermes/04_file.md#msg-792` — jumps directly to the message
- Context: messages immediately before and after
- Role, model, date, file path

### Flags
| Flag | Effect |
|------|--------|
| `--any` | OR search (default: AND — all words must match) |
| `--model <name>` | Filter by model substring |
| `--topic <name>` | Filter by topic tag |
| `--source <name>` | Filter by source folder (hermes, gpt, etc.) |
| `--context N` | Context lines in --paras mode (default 2) |
| `-n N` | Max paragraph results (default 50) |
| `--json` | JSON output for programmatic use |

## File format conventions

```
---
title: "Session title"
source: "Hermes desktop"
session_id: "20260626_221827_6d108f"
model: "claude-sonnet-4-6"
date: "2026-06-26"
exported: "2026-07-08"
topics: [проза, hermes]
message_count: 298
---

# Session title

<a id="msg-792"></a>
### Пользователь

Message text here...

<a id="msg-793"></a>
### Ассистент

Response text...
 *(инструменты: vision_analyze, terminal)*
```

## Workflow: "Find chats about project X" / "Summarize session Y by topic"

When the user asks to locate chats tied to a specific on-disk project, or to break one session into topic-organized deliverables, the workflow is **two-track, parallel**:

### Track 1 — Search the conversation DB
```bash
# Discovery (FTS5, dedupes by session, returns bookends + ±5 messages around match)
session_search(query="<project-name> OR <key-file> OR <github-url>", limit=10)

# Targeted scroll inside the matching session
session_search(session_id="<id>", around_message_id=<anchor>, window=15)
```

This tells you **which sessions** discuss the project and **where** in each session.

### Track 2 — Read the project on disk
In parallel, `find` and `read_file` the project root. Most user projects have:
- `README.md` / `BRIEF.md` / `CONTEXT.md` / `TASK.md` / `PROJECT_LOG.md` — the ground truth for *what the project is and what its sub-areas are*.
- A `tasks/done/` or `tasks/` folder with phase reports.
- `.git` history pointing at the canonical GitHub repo.

**Critical insight:** the project directory often reveals that the project is *not* a loose jumble of unrelated things — it's a single coherent project with a fixed set of sub-tasks (e.g. HERMES-ALL-IN-ONE = "install Hermes Agent" with three final goals: finance / mail / KB). The on-disk structure is more reliable than the user's loose recall of "the main topics were X, Y, Z". Read the brief first, then map the user's recall onto it.

### Track 3 — Paragraph-level deep dive (optional)
For each candidate session found in Track 1, use the LLM-KNOWLEDGE-BASE `search.py` to pull specific paragraphs with anchor links — far more precise than `session_search` for large sessions (4k+ lines / 300 messages):
```bash
cd "G:/_My_Programming/LLM-KNOWLEDGE-BASE"
python search.py --paras <keyword1> <keyword2> --any --context 2 -n 30 --source hermes
```
The output gives `chats/hermes/04_file.md#msg-792` links that you can paste into the final deliverable so the user can jump straight to the relevant chunk.

### When to use `search.py` vs `session_search`
| Need | Tool |
|------|------|
| Find which sessions touch a topic | `session_search` (built-in, FTS5) |
| Find the exact paragraph in a known session | `search.py --paras` (anchor links) |
| Read 30 messages around an anchor | `session_search(around_message_id=...)` |
| Need the message *text* of a known msg-id | `search.py --paras` + open the anchor |

---

## Workflow: "Write N topic-organized files summarizing a session"

When the user asks for `<N> files, each covering one topic from this chat`, the deliverable shape is:
1. Create a new subdirectory inside the project (e.g. `projects/`) — keeps the topic files logically separate from the BRIEF/TASK/REPORT files already in the root.
2. One `.md` per topic. Each file:
   - Title: `<Topic> — полная сводка по проекту <ProjectName>`.
   - Header block: source files, status (✅/🟡/❌), links.
   - Sections drawn from the BRIEF (phases) and the chats (concrete decisions / pitfalls / numbers).
   - Honest status flags: if a topic was only conceptually mentioned and not implemented, mark it "не начато" with a reconstruction plan, not fabricated detail.
   - Always end with "Связанные файлы" / "Что нужно сделать дальше" sections.
3. Each file **must** be written with `encoding='utf-8-sig'` (see pitfall 1) and under ~8K tokens per `write_file` call to avoid `execute_code` stream timeouts.

**Why subdirectory and not the project root:** project roots often have AGENTS.md rules like "не выходи за рамки TASK.md" or git-ignored patterns. A new subdirectory is safe and self-contained.

## Pitfalls

1. **UTF-8 BOM is mandatory.** Yuri's Markdown reader decodes BOM-less UTF-8 as Windows-1251 → mojibake. All `.md` files MUST be written with `encoding='utf-8-sig'`. Verify after write: first 3 bytes must be `EF BB BF`.
   - **BOM-OK verification without `terminal`:** use `read_file(limit=1)` and check that the first line is the heading without a `\ufeff` artefact. The BOM is invisible to `read_file`'s decoder, so its absence in the visible output = BOM is correctly present. (`terminal` calls to verify with `python -c` may be blocked or time out — don't depend on them.)

2. **`execute_code` and `write_file` calls have a per-call content size limit (~8K tokens / 15–20 KB).** Mid-session the runtime will time out and explicitly tell you to break large content into multiple smaller calls. **For multi-file deliverables:** one `write_file` per file, not one `execute_code` writing all three.

3. **Filenames must not contain spaces.** The slugify function replaces spaces with hyphens. If filenames have spaces, the search anchor links will break.

4. **Subagent sessions are noise.** Filter out `source='subagent'` sessions — they're 2-message wrappers with no meaningful content.

5. **System noise must be filtered.** Skip messages containing `"active model for this chat has changed"` and `"from this point forward, use this runtime metadata"` — these are internal Hermes announcements, not user content.

6. **Tool results under 15 chars are empty noise** — skip them.

7. **The `clarify` tool does NOT work in Yuri's desktop GUI** (returns empty response). Do not use `clarify` with him; ask questions as plain text instead.

8. **Active skills root is `%LOCALAPPDATA%\hermes\skills\` (AppData), NOT `~/.hermes/skills/`.** Hermes only scans the AppData root; `~/.hermes/skills/` is ignored. The `idea-workflow` suite (4 skills: `idea-to-design-doc`, `idea-to-ui-design-brief`, `idea-to-implementation-doc`, `idea-superpowers-suite`) now lives under the AppData category `idea-workflow\` and IS visible in `skills_list`. The third skill (`idea-to-implementation-doc`) is the one Yuri uses for ТЗ/техспек work. If any skill exists on disk but is missing from `skills_list`, check it's under the AppData root and only one category level deep (nested sub-subfolders are not scanned) — copy it into place, then verify with `skills_list`.

9. **For "summarize this big session by topic" requests, the user's recall of "the main topics were X, Y, Z" may be wrong or incomplete.** Cross-check against the project's BRIEF/CONTEXT/TASK files before committing to the topic list — the on-disk documents are the source of truth. If the user lists three topics and the project actually has four, surface the discrepancy in your reply rather than silently omitting the fourth.

10. **Mark statuses honestly in deliverables.** If a topic was mentioned only conceptually (e.g. "почтовый триаж — задача №1, вне охвата текущего брифа"), write the file with status "❌ не начато" + a reconstructed plan + what's known — do not invent implementation details to fill the file.

## Future sources (phase 2)

- `chats/gpt/` — export from ChatGPT (JSON export)
- `chats/gemini/` — export from Gemini
- `chats/grok/` — export from Grok
- `chats/perplexity/` — export from Perplexity
- `chats/claude-web/` — export from claude.ai

## Annex: Archive workflow — multi-axis session classification

When the goal is **not** to export all sessions to searchable files, but to *curate* them into condensed theme/project/type summaries (e.g. for a knowledge base build), use the 3-axis classification:

| Axis | Directory | Description |
|------|-----------|-------------|
| **PROJECTS** | `.../ARCHIVE/PROJECTS/` | Sessions tied to a specific on-disk project directory (cwd matches project root). One `.docx` per project. |
| **THEME** | `.../ARCHIVE/THEME/` | Sessions about an abstract topic (NSFW-проза, финансы, ComfyUI) with no fixed project dir. |
| **SESSION TYPES** | `.../ARCHIVE/SESSION TYPES/` | Character of work: `task` (TASK.md→REPORT.md), `explore` (research), `reminder` (cron), `dead` (≤5 msg), `chat` (free-form). |

One session can appear in multiple axes (e.g. tagged project=HERMES-ALL-IN-ONE AND theme=git-sync). The axes are cross-cutting — identical.

### Workflow steps

1. **Inventory** — `SELECT id, title, started_at, cwd FROM sessions ORDER BY started_at`
2. **Move sessions** by `cwd` matching known project roots → map to PROJECTS
3. **Classify remainder** by title + first user message → map to THEME and TYPE
4. **Extract messages** for each group chronologically
5. **Build output** — one `.docx` per project/theme/type using `python-docx`
   - Title + summary
   - Sessions in chronological order with full dialogue
   - Metadata table per session (ID, model, date, msg count)
   - Key decisions / выводы section at the end

### SQL queries for extraction

See `references/archive-workflow.md` for ready-to-run queries.

### Output format (.docx)

Use `python-docx` (available in Yuri's env, version 1.2.0). Document structure:
1. Title page (centred, subtitle "Сводка сессий по проекту • хронология • ключевые решения")
2. Общая сводка — 1 paragraph describing the project/theme
3. Хронология сессий — each session as H2 heading + metadata table + dialogue
4. Ключевые решения и выводы — bullet list
5. Привязанные директории

### Pitfalls

- **`write_file` does NOT understand MSYS paths** (`/g/...` resolves to `C:\g\...`). Always use native `G:/...` or `C:/Users/...` in Python scripts passed to `terminal`. Verify output file location with `ls` after creation.
- **`python-docx` must be called via `terminal`**, not `execute_code`, because the output lands on a G:-drive path that `execute_code` can't write to.
- **Check message count** before extraction: sessions with 250+ messages × 3K chars each produce a large `.docx`. Truncate individual messages > 3000 chars in the doc.
- **Separate current session** from archived ones — the active session (today's) is still being written to and shouldn't be in the archive yet.

## References

- `references/schema.md` — state.db schema, key queries, noise filter patterns
- `references/archive-workflow.md` — SQL queries for 3-axis session classification and .docx build instructions
- `references/compile-architecture.md` — compile.py layered guards, hash logic, page validation, and selftest patterns (TASK-021)
- Google Drive sync via `google-workspace` skill

## Приложения, перенесённые из отдельных скиллов

Эти скиллы раньше жили отдельно и были вычищены curator'ом; содержание перенесено сюда целиком, чтобы знание не терялось.

- `references/llm-chat-knowledge-base.md` — Export, organize, and search chat histories from LLM platforms (Hermes, GPT, Gemini, Grok, Perplexity, Claude) as a local markdown knowledge base with document-level and paragraph-level search.
  - `scripts\export_hermes.py`
  - `scripts\search_kb.py`
